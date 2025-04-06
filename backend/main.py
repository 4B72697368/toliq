from flask import Flask, request, jsonify
from flask_cors import CORS
from functions import functions
import openai
import dotenv
import os
import re
import json

app = Flask(__name__)
CORS(
    app,
    resources={
        r"/*": {
            "origins": ["http://localhost:3000", "http://127.0.0.1:3000", "*"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    },
)

dotenv.load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")

with open("connections.json", "r") as f:
    connectionsDoc = f.read()

prompt = """You are a helpful AI assistant that can interact with various functions. When a user makes a request:

1. First make any necessary function calls using this EXACT XML format:
<function_call>
  <platform>platform_name</platform>
  <function>function_name</function>
  <parameters>
    <parameter name="param1">value1</parameter>
    <parameter name="param2">value2</parameter>
  </parameters>
</function_call>

2. After making a function call that returns data, ALWAYS use:
<function_call>
  <platform>io</platform>
  <function>continue</function>
  <parameters></parameters>
</function_call>

3. When you receive the function results in the next prompt:
   - DO NOT say what you will do or explain your next steps
   - DO NOT include any text, explanations, or plan outside of the function call tags
   - If you need to make another function call based on the results, IMMEDIATELY make that call
   - If no more calls are needed, provide a detailed analysis/response based on the data
   - Then end with: 
<function_call>
  <platform>io</platform>
  <function>end</function>
  <parameters></parameters>
</function_call>

4. If you need to make another function call after analyzing data:
   - Make the call IMMEDIATELY using the XML format
   - DO NOT include any explanatory text before or after the XML
   - When you get those results, either make another call or analyze them
   - End with io.end


CRITICAL RULES:
1. ALWAYS wrap ALL your responses in function call tags. NEVER output plain text in between function calls.
2. Parameters MUST be enclosed in <parameter> tags with name attribute:
   CORRECT:
   <parameters>
     <parameter name="sheet_name">Sheet1</parameter>
     <parameter name="cells">{"A1": {"value": 1}}</parameter>
   </parameters>
   
   INCORRECT:
   <parameters>
     "sheet_name": "Sheet1",
     "cells": {"A1": {"value": 1}}
   </parameters>

3. For JSON values (like cells/formulas), include the JSON directly inside the parameter tags:
   CORRECT: <parameter name="cells">{"A1": {"value": 1}}</parameter>
   INCORRECT: <parameter name="cells">"{"A1": {"value": 1}}"</parameter>

4. NEVER escape quotes in JSON values
5. NEVER ask the user for extra information - just follow the command as best you can
6. When you receive function results, DO NOT say what you will do - just make the next function call
7. On re-prompt after receiving function results, IMMEDIATELY make the next call if one is needed
8. You cannot directly access or modify data - you must always make function calls to do so.
9. IMPORTANT: Your response must ALWAYS be in the XML format. NEVER respond with plain text, plans, or explanations outside the function calls.

EXAMPLES:

Input: "Create a formula to sum all values in column A"

CORRECT:
<function_call>
  <platform>gsheets</platform>
  <function>write_cells</function>
  <parameters>
    <parameter name="cells">{"B1": {"formula": "=SUM(A:A)"}}</parameter>
  </parameters>
</function_call>

INCORRECT:
Let me create a formula to sum all values in column A:
<function_call>
  <platform>gsheets</platform>
  <function>write_cells</function>
  <parameters>
    <parameter name="cells">{"B1": {"formula": "=SUM(A:A)"}}</parameter>
  </parameters>
</function_call>

EXAMPLE OF FLOW:
1. User asks to calculate sum in column B
2. You call gsheets.read_sheet to get data
3. You immediately call gsheets.write_cells to apply formula
4. You end with io.end
"""
prompt += connectionsDoc
prompt += "the current date, time, and timezone is: " + str(
    functions.datetime.get_current_time({"user": "system"})
)
prompt += """
CRITICAL REMINDER:
Your ENTIRE response must be in the XML function call format. Do not include ANY text, explanations, or plans outside of the <function_call> tags.

For example, to call gsheets.write_cells, only respond with:
<function_call>
  <platform>gsheets</platform>
  <function>write_cells</function>
  <parameters>
    <parameter name="cells">{"A2": {"value": "8:00-9:00"}, "B2": {"value": "Breakfast"}, "A3": {"value": "9:00-10:00"}, "B3": {"value": "Exercise"}}</parameter>
  </parameters>
</function_call>
"""


def extract_all_calls(input_str):
    """Extract function calls using the XML format"""
    calls = []

    # First check if there are any function_call tags
    if "<function_call>" not in input_str:
        print("=== No <function_call> tags found in output")
        # Look for potential malformed XML
        if "< function_call>" in input_str or "<function_call >" in input_str:
            print("=== WARNING: Found malformed function_call tags with extra spaces")

        # Check for JSON-style calls
        if "<call:" in input_str:
            print("=== Found old-style <call: format, will attempt to extract")
            # Extract using old method
            calls_from_old_format = extract_calls_old_format(input_str)
            if calls_from_old_format:
                print(
                    f"=== Successfully extracted {len(calls_from_old_format)} calls using old format"
                )
                return calls_from_old_format

    # Find all function call blocks
    pattern = r"<function_call>(.*?)</function_call>"
    function_blocks = re.findall(pattern, input_str, re.DOTALL)

    if not function_blocks:
        print("=== No function blocks matched the regex pattern")
        print(
            f"=== Output snippet: {input_str[:200]}...{input_str[-200:] if len(input_str) > 400 else ''}"
        )

    for i, block in enumerate(function_blocks):
        try:
            print(f"=== Processing function block {i+1}/{len(function_blocks)}")

            # Extract platform
            platform_match = re.search(
                r"<platform>([\s\S]*?)</platform>", block, re.DOTALL
            )
            platform = platform_match.group(1).strip() if platform_match else ""

            if not platform:
                print(f"=== WARNING: No platform found in block: {block[:100]}...")
                continue

            # Extract function
            function_match = re.search(
                r"<function>([\s\S]*?)</function>", block, re.DOTALL
            )
            function = function_match.group(1).strip() if function_match else ""

            if not function:
                print(f"=== WARNING: No function found in block: {block[:100]}...")
                continue

            # Extract parameters
            parameters = []
            param_pattern = r'<parameter\s+name="([^"]+)">([\s\S]*?)</parameter>'
            param_matches = re.findall(param_pattern, block, re.DOTALL)

            if not param_matches and "<parameters>" in block:
                print(
                    f"=== Parameters tag exists but no parameters found in block: {block[:100]}..."
                )

            for name, value in param_matches:
                print(f"=== Found parameter: {name}")
                value_preview = value[:50] + ("..." if len(value) > 50 else "")
                print(f"=== Parameter value: {value_preview}")

                # Try to parse JSON values
                try:
                    if value.strip().startswith("{") or value.strip().startswith("["):
                        parsed_value = json.loads(value)
                        print(f"=== Successfully parsed parameter value as JSON")
                        parameters.append({"name": name.strip(), "value": parsed_value})
                    else:
                        # Keep as string if not JSON
                        parameters.append({"name": name.strip(), "value": value})
                except json.JSONDecodeError as e:
                    print(f"=== Error parsing parameter value as JSON: {str(e)}")
                    # Try fixing common issues with escaped quotes
                    try:
                        fixed_value = value.replace('\\"', '"').replace('\\\\"', '\\"')
                        parsed_value = json.loads(fixed_value)
                        print(
                            f"=== Successfully parsed parameter value after fixing escapes"
                        )
                        parameters.append({"name": name.strip(), "value": parsed_value})
                    except:
                        # If still failing, keep as string
                        print(
                            f"=== Using raw string for parameter value after JSON parsing failed"
                        )
                        parameters.append({"name": name.strip(), "value": value})

            # Create the function call object
            if platform and function:
                calls.append(
                    {
                        "platform": platform,
                        "function": function,
                        "parameters": parameters,
                    }
                )
                print(
                    f"=== Successfully extracted call: {platform}.{function} with {len(parameters)} parameters"
                )
        except Exception as e:
            print(f"=== Error parsing function call block: {str(e)}")
            print(f"=== Block: {block[:100]}...")

    print(f"=== Total extracted function calls: {len(calls)}")
    return calls


def extract_calls_old_format(input_str):
    """Extracts function calls using the old <call:{...}> format for backward compatibility"""
    calls = []
    start = 0
    while True:
        start = input_str.find("<call:", start)
        if start == -1:
            break

        brace_start = input_str.find("{", start)
        if brace_start == -1:
            break

        brace_count = 1
        pos = brace_start + 1

        while brace_count > 0 and pos < len(input_str):
            if input_str[pos] == "{":
                brace_count += 1
            elif input_str[pos] == "}":
                brace_count -= 1
            pos += 1

        if brace_count == 0:
            json_str = input_str[brace_start:pos]
            try:
                parsed = json.loads(json_str)
                calls.append(parsed)
                print(
                    f"=== Extracted legacy call: {parsed.get('platform', 'unknown')}.{parsed.get('function', 'unknown')}"
                )
            except json.JSONDecodeError as e:
                print(f"=== Error parsing legacy call JSON: {str(e)}")
                print(f"=== JSON string: {json_str[:100]}...")

        start = pos

    return calls


def clean_json_for_prompt(json_str):
    """Clean up JSON to reduce redundant escaping and spacing"""
    try:
        if not isinstance(json_str, str):
            return json.dumps(json_str, separators=(",", ":"))

        json_str = json_str.replace('\\"', '"').replace("\\\\", "\\")

        parsed = json.loads(json_str)
        return json.dumps(parsed, separators=(",", ":"))
    except:
        return json_str


def format_function_result(platform, function, result):
    """Format function results consistently and cleanly using XML format"""
    try:
        # Convert to string representation
        if isinstance(result, dict) or isinstance(result, list):
            result_str = json.dumps(result, separators=(",", ":"))
        elif isinstance(result, str):
            # If it's already a string but could be JSON, try to parse and re-serialize it
            try:
                json_obj = json.loads(result)
                result_str = json.dumps(json_obj, separators=(",", ":"))
            except:
                # Not valid JSON, keep as is
                result_str = result
        else:
            # For other types, just convert to string
            result_str = str(result)

        return f"""<function_result>
  <platform>{platform}</platform>
  <function>{function}</function>
  <result>{result_str}</result>
</function_result>"""
    except Exception as e:
        print(f"Error formatting function result: {e}")
        # Safe fallback
        return f"""<function_result>
  <platform>{platform}</platform>
  <function>{function}</function>
  <result>Error formatting result: {str(e)}</result>
</function_result>"""


def handle_message(input, call_responses, user, output="", depth=0):
    function_calls_trace = []

    try:
        connections = json.loads(connectionsDoc)
        clean_connections = json.dumps(connections, separators=(",", ":"))

        system_prompt = prompt + clean_connections

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input},
        ]

        for response in call_responses:
            if '"platform":"io"' in response.replace(
                " ", ""
            ) and '"function":"continue"' in response.replace(" ", ""):
                continue

            if "Result of" in response:
                try:
                    start = response.find("{")
                    end = response.rfind("}") + 1
                    if start >= 0 and end > start:
                        json_part = response[start:end]
                        cleaned_json = clean_json_for_prompt(json_part)
                        response = response[:start] + cleaned_json + response[end:]
                except Exception as json_error:
                    print(
                        f"Error cleaning JSON: {str(json_error)}, response: {response[:100]}"
                    )

            messages.append({"role": "assistant", "content": response})

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
        )
        current_output = response.choices[0].message.content
        calls = extract_all_calls(current_output)

        should_continue = False
        found_end = False
        for i, call in enumerate(calls):
            print(f"Processing call: {json.dumps(call)}")
            if call["platform"] == "io":
                if call["function"] == "continue":
                    should_continue = True
                elif call["function"] == "end":
                    found_end = True
                function_calls_trace.append(
                    {
                        "platform": call["platform"],
                        "function": call["function"],
                        "parameters": call["parameters"],
                    }
                )
                continue

            function_calls_trace.append(
                {
                    "platform": call["platform"],
                    "function": call["function"],
                    "parameters": call["parameters"],
                }
            )

            execution = (
                "functions."
                + call["platform"]
                + "."
                + call["function"]
                + "("
                + "user=user, "
            )
            params = []
            for param in call["parameters"]:
                params.append(f"{param['name']}={repr(param['value'])}")
            execution += ", ".join(params) + ")"

            print(f"Executing: {execution}")
            try:
                # Add function call details to call_responses in XML format
                parameters_xml = ""
                for param in call["parameters"]:
                    param_name = param["name"]
                    param_value = param["value"]

                    # Format value based on type
                    if isinstance(param_value, (dict, list)):
                        param_value_str = json.dumps(param_value, separators=(",", ":"))
                    else:
                        param_value_str = str(param_value)

                    parameters_xml += f'    <parameter name="{param_name}">{param_value_str}</parameter>\n'

                call_info = f"""<function_call>
  <platform>{call['platform']}</platform>
  <function>{call['function']}</function>
  <parameters>
{parameters_xml}  </parameters>
</function_call>"""

                call_responses.append(call_info)

                result = eval(execution)
                result_message = format_function_result(
                    call["platform"], call["function"], result
                )
                call_responses.append(result_message)

                if call["platform"] in connections:
                    platform_info = connections[call["platform"]]
                    if isinstance(platform_info, dict):
                        if "functions" in platform_info:
                            function_info = platform_info["functions"].get(
                                call["function"], {}
                            )
                        else:
                            function_info = platform_info.get(call["function"], {})

                        if function_info.get("output") == True:
                            should_continue = True
                            call_responses.append(
                                "<function_call><platform>io</platform><function>continue</function><parameters></parameters></function_call>"
                            )
            except Exception as e:
                error_msg = f"Error in {call['platform']}.{call['function']}: {str(e)}"
                print(error_msg)
                import traceback

                print(traceback.format_exc())
                call_responses.append(error_msg)

        if should_continue:
            next_result = handle_message(input, call_responses, user, output, depth + 1)
            print(f"Continuing from depth {depth} to {depth+1}")
            if "function_calls_trace" in next_result:
                function_calls_trace.extend(next_result["function_calls_trace"])
            return {
                "output": next_result["output"],
                "call_responses": next_result["call_responses"],
                "complete": next_result["complete"],
                "function_calls_trace": function_calls_trace,
            }

        if found_end or (not calls and not should_continue):
            return {
                "output": current_output,
                "call_responses": call_responses,
                "complete": True,
                "function_calls_trace": function_calls_trace,
            }

        next_result = handle_message(input, call_responses, user, output, depth + 1)
        print(f"Moving to next step from depth {depth} to {depth+1}")
        if "function_calls_trace" in next_result:
            function_calls_trace.extend(next_result["function_calls_trace"])
        return {
            "output": next_result["output"],
            "call_responses": next_result["call_responses"],
            "complete": next_result["complete"],
            "function_calls_trace": function_calls_trace,
        }

    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        print(f"EXCEPTION in handle_message at depth {depth}: {str(e)}")
        print(f"Traceback: {error_traceback}")
        return {
            "error": f"Error at depth {depth}: {str(e)}",
            "complete": True,
            "function_calls_trace": function_calls_trace,
        }


@app.route("/message", methods=["POST", "OPTIONS"])
def handle_request():
    if request.method == "OPTIONS":
        return "", 200

    try:
        data = request.get_json()

        if not data or "input" not in data:
            return jsonify({"error": "Missing 'input' in JSON body"}), 400

        user_input = data["input"]
        user = data["user"]

        # Get conversation history if available
        conversation_history = data.get("conversation_history", [])

        # Format previous messages for context if available
        context = ""
        if (
            conversation_history and len(conversation_history) > 1
        ):  # More than just the current message
            # Format the last few messages as context (excluding the current message)
            context = "Previous conversation:\n"
            for i, msg in enumerate(
                conversation_history[:-1]
            ):  # All except the last one
                role = "User" if msg.get("role") == "user" else "Assistant"
                context += f"{role}: {msg.get('content', '')}\n"

            context += "\nCurrent request:\n"

            # Prepend context to the current input
            user_input = context + user_input

        print(f"Processing request with input: {user_input[:50]}...")

        result = handle_message(user_input, [], user=user)
        while not result.get("complete", False):
            result = handle_message(
                user_input,
                result.get("call_responses", []),
                user=user,
                output=result.get("output", ""),
            )

        if "error" in result:
            error_msg = result["error"]
            print(f"ERROR in handle_message: {error_msg}")
            return jsonify({"error": error_msg}), 500

        return jsonify(
            {
                "output": result["output"],
                "call_responses": result.get("call_responses", []),
            }
        )
    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        print(f"EXCEPTION in handle_request: {str(e)}")
        print(f"Traceback: {error_traceback}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
