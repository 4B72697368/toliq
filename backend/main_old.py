from flask import Flask, request, jsonify
from functions import functions
import openai
import dotenv
import os
import re
import json
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configure OpenAI debug logging
openai_logger = logging.getLogger("openai")
openai_logger.setLevel(logging.DEBUG)

app = Flask(__name__)

dotenv.load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")

with open("connections.json", "r") as f:
    connectionsDoc = f.read()
    logger.debug("Loaded connections.json: %s", connectionsDoc[:100] + "...")

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
    functions.datetime.get_current_time()
)
print("time: " + str(functions.datetime.get_current_time()))


def extract_all_calls(input_str):
    logger.debug("Extracting calls from input: %s", input_str)

    # Find all occurrences of <call:...> with balanced braces
    calls = []
    start = 0
    while True:
        # Find the next <call: marker
        call_start = input_str.find("<call:", start)
        if call_start == -1:
            break

        # Find the closing > after the JSON
        call_end = input_str.find(">", call_start)
        if call_end == -1:
            break

        # Extract just the JSON part
        json_str = input_str[call_start + 6 : call_end]  # +6 to skip "<call:"
        try:
            parsed = json.loads(json_str)
            logger.debug("Successfully parsed JSON: %s", json.dumps(parsed, indent=2))
            calls.append(parsed)
        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON: %s\nError: %s", json_str, e)

        start = call_end + 1

    logger.debug("Found %d calls", len(calls))
    return calls


def clean_json_for_prompt(json_str):
    """Clean up JSON to reduce redundant escaping and spacing"""
    try:
        # If it's already a dict/list, just serialize it
        if not isinstance(json_str, str):
            return json.dumps(json_str, separators=(",", ":"))

        # Remove redundant escaping
        json_str = json_str.replace('\\"', '"').replace("\\\\", "\\")

        # Parse and re-serialize without pretty printing
        parsed = json.loads(json_str)
        return json.dumps(parsed, separators=(",", ":"))
    except:
        return json_str


def format_function_result(platform, function, result):
    """Format function results consistently and cleanly"""
    try:
        if isinstance(result, str):
            # Try to parse if it's a JSON string
            try:
                result = json.loads(result)
            except:
                pass
        return f"Result of {platform}.{function}: {json.dumps(result, separators=(',', ':'))}"
    except:
        return f"Result of {platform}.{function}: {result}"


def handle_message(input, call_responses, output="", depth=0):
    logger.debug("\n%sEntering handle_message (depth=%d)", "  " * depth, depth)
    logger.debug("%sInput: %s", "  " * depth, input)
    logger.debug("%sCall responses length: %d", "  " * depth, len(call_responses))

    # Track function calls
    function_calls_trace = []

    try:
        # Load and clean connections doc once
        connections = json.loads(connectionsDoc)
        clean_connections = json.dumps(connections, separators=(",", ":"))

        # Build system prompt with cleaned JSON
        system_prompt = prompt + clean_connections

        # Construct conversation history
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input},  # Always keep original instruction
        ]

        # Add all previous responses and results in sequence
        for response in call_responses:
            # Skip io.continue calls in the context
            if '"platform":"io"' in response.replace(
                " ", ""
            ) and '"function":"continue"' in response.replace(" ", ""):
                continue

            # Clean up JSON in responses
            if "Result of" in response:
                try:
                    start = response.find("{")
                    end = response.rfind("}") + 1
                    if start >= 0 and end > start:
                        json_part = response[start:end]
                        cleaned_json = clean_json_for_prompt(json_part)
                        response = response[:start] + cleaned_json + response[end:]
                except:
                    pass

            messages.append({"role": "assistant", "content": response})

        logger.debug("%sConstructed conversation history:", "  " * depth)
        for i, msg in enumerate(messages):
            logger.debug(
                "%sMessage %d - %s: %s",
                "  " * depth,
                i,
                msg["role"],
                msg["content"][:100] + "...",
            )

        logger.debug(
            "\n%sSending request to OpenAI with %d messages",
            "  " * depth,
            len(messages),
        )
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,  # Add some variability to avoid getting stuck in loops
        )
        current_output = response.choices[0].message.content
        logger.debug(
            "\n%sReceived response from OpenAI: %s", "  " * depth, current_output
        )

        # Extract any function calls
        calls = extract_all_calls(current_output)
        logger.debug("%sExtracted %d calls", "  " * depth, len(calls))

        # Process function calls
        should_continue = False
        found_end = False
        for i, call in enumerate(calls):
            logger.debug(
                "%sProcessing call %d: %s", "  " * depth, i, json.dumps(call, indent=2)
            )

            if call["platform"] == "io":
                if call["function"] == "continue":
                    logger.debug(
                        "%sFound io.continue, will recurse after processing all calls",
                        "  " * depth,
                    )
                    should_continue = True
                elif call["function"] == "end":
                    logger.debug("%sFound io.end, marking as complete", "  " * depth)
                    found_end = True
                # Track io calls too
                function_calls_trace.append(
                    {
                        "platform": call["platform"],
                        "function": call["function"],
                        "parameters": call["parameters"],
                    }
                )
                continue

            # Track non-io function call
            function_calls_trace.append(
                {
                    "platform": call["platform"],
                    "function": call["function"],
                    "parameters": call["parameters"],
                }
            )

            execution = "functions." + call["platform"] + "." + call["function"] + "("
            params = []
            for param in call["parameters"]:
                params.append(f"{param['name']}={repr(param['value'])}")
            execution += ", ".join(params) + ")"

            logger.debug("%sExecuting: %s", "  " * depth, execution)

            try:
                result = eval(execution)
                logger.debug(
                    "%sFunction result: %s", "  " * depth, json.dumps(result, indent=2)
                )

                # Format result consistently
                result_message = format_function_result(
                    call["platform"], call["function"], result
                )
                call_responses.append(result_message)
                logger.debug(
                    "%sAdded result to call_responses: %s", "  " * depth, result_message
                )

                # Check if function has output flag
                if call["platform"] in connections:
                    platform_info = connections[call["platform"]]
                    if isinstance(platform_info, dict):
                        # Handle both old and new format
                        if "functions" in platform_info:
                            function_info = platform_info["functions"].get(
                                call["function"], {}
                            )
                        else:
                            function_info = platform_info.get(call["function"], {})

                        if function_info.get("output") == True:
                            logger.debug(
                                "%sFunction had output flag, will continue",
                                "  " * depth,
                            )
                            should_continue = True
                            # Force continuation after this call
                            call_responses.append(
                                '<call:{"platform":"io","function":"continue","parameters":[]}>'
                            )
            except Exception as e:
                logger.error("%sError executing function: %s", "  " * depth, str(e))
                logger.error("%sTraceback: %s", "  " * depth, traceback.format_exc())
                call_responses.append(
                    f"Error in {call['platform']}.{call['function']}: {str(e)}"
                )

        # After processing all calls, continue if needed
        if should_continue:
            logger.debug("%sContinuing with accumulated responses", "  " * depth)
            next_result = handle_message(input, call_responses, output, depth + 1)
            # Merge function calls from recursive call
            if "function_calls_trace" in next_result:
                function_calls_trace.extend(next_result["function_calls_trace"])
            return {
                "output": next_result["output"],
                "call_responses": next_result["call_responses"],
                "complete": next_result["complete"],
                "function_calls_trace": function_calls_trace,
            }

        # Only complete if we found an explicit end call or have no more calls to make
        if found_end or (not calls and not should_continue):
            logger.debug(
                "%sCompleting - found_end: %s, no_calls: %s",
                "  " * depth,
                found_end,
                not calls,
            )
            return {
                "output": current_output,
                "call_responses": call_responses,
                "complete": True,
                "function_calls_trace": function_calls_trace,
            }

        # Otherwise, get another response
        logger.debug(
            "%sNo end found and no continuation needed, getting another response",
            "  " * depth,
        )
        next_result = handle_message(input, call_responses, output, depth + 1)
        # Merge function calls from recursive call
        if "function_calls_trace" in next_result:
            function_calls_trace.extend(next_result["function_calls_trace"])
        return {
            "output": next_result["output"],
            "call_responses": next_result["call_responses"],
            "complete": next_result["complete"],
            "function_calls_trace": function_calls_trace,
        }

    except Exception as e:
        logger.error("%sError in handle_message: %s", "  " * depth, str(e))
        logger.error("%sError type: %s", "  " * depth, type(e))
        import traceback

        logger.error("%sTraceback: %s", "  " * depth, traceback.format_exc())
        return {
            "error": str(e),
            "complete": True,
            "function_calls_trace": function_calls_trace,
        }


@app.route("/message", methods=["POST"])
def handle_request():
    logger.debug("\nReceived new request")
    data = request.get_json()
    logger.debug("Request data: %s", json.dumps(data, indent=2))

    if not data or "input" not in data:
        logger.error("Missing 'input' in request data")
        return jsonify({"error": "Missing 'input' in JSON body"}), 400

    user_input = data["input"]
    logger.debug("Processing user input: %s", user_input)

    # Process until complete
    result = handle_message(user_input, [])
    while not result.get("complete", False):
        result = handle_message(
            user_input, result.get("call_responses", []), result.get("output", "")
        )

    # Return final result
    if "error" in result:
        return jsonify({"error": result["error"]}), 500
    return jsonify(
        {"output": result["output"], "call_responses": result.get("call_responses", [])}
    )


if __name__ == "__main__":
    app.run(debug=True)
