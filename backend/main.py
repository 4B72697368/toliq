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

1. First make any necessary function calls using this EXACT format:
<call:{"platform": "platform_name", "function": "function_name", "parameters": [{"name": "param1", "value": "value1"}]}>

2. After making a function call that returns data, ALWAYS use:
<call:{"platform": "io", "function": "continue", "parameters": []}>

3. When you receive the function results in the next prompt:
   - DO NOT say what you will do or explain your next steps
   - If you need to make another function call based on the results, IMMEDIATELY make that call
   - If no more calls are needed, provide a detailed analysis/response based on the data
   - Then end with: <call:{"platform": "io", "function": "end", "parameters": []}>

4. If you need to make another function call after analyzing data:
   - Make the call IMMEDIATELY without explanation
   - Use io.continue
   - When you get those results, either make another call or analyze them
   - End with io.end


CRITICAL RULES:
1. Parameters MUST be an array of objects, each with "name" and "value" fields:
   CORRECT:
   "parameters": [
     {"name": "sheet_name", "value": "Sheet1"},
     {"name": "cells", "value": {"A1": {"value": 1}}}
   ]
   
   INCORRECT:
   "parameters": {
     "sheet_name": "Sheet1",
     "cells": {"A1": {"value": 1}}
   }

2. For JSON values (like cells/formulas), put the JSON directly in the "value" field:
   CORRECT: {"name": "cells", "value": {"A1": {"value": 1}}}
   INCORRECT: {"name": "cells", "value": "{\\"A1\\": {\\"value\\": 1}}"}

3. NEVER escape quotes in JSON values
4. NEVER ask the user for extra information - just follow the command as best you can
5. When you receive function results, DO NOT say what you will do - just do it
6. NEVER explain your next steps - just execute them
7. On re-prompt after receiving function results, IMMEDIATELY make the next call if one is needed
8. IMPORTANT: NEVER fabricate or hallucinate function results. Do not include "Result of [function]" text in your responses. Only the system will provide real function results.
9. You cannot directly access or modify data - you must always make function calls to do so.
10. Never pretend a function was called when it wasn't. Always wait for actual system response showing function results.
11. Specifically, NEVER say "Result of calendar.create_events: {...}" - instead, you must make the actual function call using:
    <call:{"platform":"calendar","function":"create_events","parameters":[{"name":"events","value":[...]}]}>
12. If a task has not been explicitly completed in the context, you MUST call the necessary functions to complete it. On each prompt, if you don't see evidence that a requested operation was performed, assume it still needs to be done. Continue making function calls until the task is complete.
13. Always check if the requested operation appears in the previous function calls before claiming it's done. If you don't see evidence that a specific function was called and returned results, you MUST make that function call.
14. With each function call, include a brief plan of all steps needed for the task. Format as follows:
    Plan: 
    - Step 1: [Description] ✓
    - Step 2: [Description] (current)
    - Step 3: [Description]
    
    Mark completed steps with a checkmark (✓) and indicate the current step with "(current)".
    after that, you must make the function call to complete the next task.
"""
prompt += connectionsDoc
prompt += "the current date, time, and timezone is: " + str(
    functions.datetime.get_current_time({"user": "system"})
)


def extract_all_calls(input_str):
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
            parsed = json.loads(json_str)
            calls.append(parsed)

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
    """Format function results consistently and cleanly"""
    try:
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except:
                pass
        return f"Result of {platform}.{function}: {json.dumps(result, separators=(',', ':'))}"
    except:
        return f"Result of {platform}.{function}: {result}"


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
                                '<call:{"platform":"io","function":"continue","parameters":[]}>'
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
