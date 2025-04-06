from flask import Flask, request, jsonify
from functions import functions
import openai
import dotenv
import os
import re
import json
from IPython import embed

app = Flask(__name__)

dotenv.load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")

with open("connections.json", "r") as f:
    connectionsDoc = f.read()

prompt = """Your role is to ONLY output function calls in response to user requests. Use this EXACT format:
<call:{"platform": "platform_name", "function": "function_name", "parameters": [{"name": "param1", "value": "simple_value"}]}> (never use newlines in the <call>)

CRITICAL RULES:
1. For JSON parameters (like cells/formulas), the value must be a plain JSON object, NOT a string
2. Example of correct JSON parameter:
   {"name": "cells", "value": {"A1": {"value": 1}, "B1": {"value": 2}}}
3. Example of INCORRECT JSON parameter (DO NOT DO THIS):
   {"name": "cells", "value": "{\\"A1\\": {\\"value\\": 1}}"}
4. NEVER escape quotes in JSON values
5. NEVER ask the user for extra information - just follow the command as best you can
6. NEVER include type, example, or description fields from the docs
7. NEVER output any explanatory text - ONLY output the function call
8. If you need to do multiple steps or use output from a previous call, use io.continue

The available functions are defined in this doc:"""
prompt += connectionsDoc


def extract_all_calls(input_str):
    # Use a non-greedy match to find content between <call: and >
    matches = re.findall(r"<call:(\{.*?\})>", input_str)
    print("Found matches:", len(matches))

    calls = []
    for m in matches:
        try:
            print("\nAttempting to parse JSON:", repr(m))
            # Parse the JSON directly
            parsed = json.loads(m)
            print("Successfully parsed JSON")
            calls.append(parsed)
        except json.JSONDecodeError as e:
            print(f"Failed to decode: {m}\nError: {e}")
            continue

    return calls


def handle_message(input, call_responses, output=""):
    try:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": input},
        ]
        for i in call_responses:
            messages += [{"role": "assistant", "content": i}]

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", messages=messages
        )
        current_output = response["choices"][0]["message"]["content"]
        output += current_output + "break"
        print("\nLLM Output:", repr(current_output))

        calls = extract_all_calls(current_output)
        print("\nExtracted calls:", len(calls))

        for call in calls:
            if call["platform"] == "io" and call["function"] == "continue":
                return handle_message(input, call_responses, output)

            execution = "functions." + call["platform"] + "." + call["function"] + "("
            for parameter_index in range(0, len(call["parameters"])):
                parameter = call["parameters"][parameter_index]
                # For JSON string values, ensure they're complete
                if isinstance(parameter["value"], str):
                    if parameter["value"].startswith("{"):
                        try:
                            # Try to parse it as JSON to validate
                            json_obj = json.loads(parameter["value"])
                            # Re-serialize to ensure proper formatting
                            parameter["value"] = json.dumps(json_obj)
                        except json.JSONDecodeError as e:
                            print(f"JSON validation error: {e}")
                            # Fix common issues with formula strings
                            value = parameter["value"]
                            # Ensure the string ends with a proper closing brace
                            if not value.rstrip().endswith("}"):
                                value = value.rstrip() + "}"
                            try:
                                # Validate the fixed JSON
                                json_obj = json.loads(value)
                                parameter["value"] = json.dumps(json_obj)
                            except json.JSONDecodeError:
                                print("Warning: Could not validate fixed JSON")
                                # If validation fails, at least ensure proper JSON structure
                                if value.count("{") > value.count("}"):
                                    value = value.rstrip() + "}"
                                parameter["value"] = value
                            print("Fixed value:", repr(parameter["value"]))

                execution += f"{parameter['name']}={repr(parameter['value'])}"
                if parameter_index != len(call["parameters"]) - 1:
                    execution += ", "
            execution += ")"
            print("\nExecuting:", execution)
            # embed(local=locals())

            # Check if function has output
            if call["platform"] in json.loads(connectionsDoc):
                platform_info = json.loads(connectionsDoc)[call["platform"]]
                if isinstance(platform_info, dict) and "functions" in platform_info:
                    function_info = platform_info["functions"].get(call["function"], {})
                    if function_info.get("output") == True:
                        result = eval(execution)
                        call_responses.append(
                            f"Output from call: {str(call)} is the following: {str(result)}"
                        )
                    else:
                        exec(execution)

        return jsonify({"output": output})

    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route("/message", methods=["POST"])
def handle_request():
    data = request.get_json()

    if not data or "input" not in data:
        return jsonify({"error": "Missing 'input' in JSON body"}), 400

    user_input = data["input"]
    return handle_message(user_input, [])


if __name__ == "__main__":
    app.run(debug=True)
