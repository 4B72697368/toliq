from flask import Flask, request, jsonify
from functions import functions
import openai
import dotenv
import os
import re
import json

app = Flask(__name__)

dotenv.load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")

with open("connections.json", "r") as f:
    connectionsDoc = f.read()

prompt = "You are an assistant tasked with helping the user, you have the ability to call different functions, according to the following doc: + \n"
prompt += connectionsDoc
prompt += "\n This is the structure of a call: <call:{\"platform\": \"test_platform\", \"function\": \"led\", \"parameters\": [{\"name\": \"duration\", \"value\": \"30\"}]}> You are to use this exact structure at all times."
prompt += "\n For example, if the user asks for you to set the led based on the state of robot 2, you do call robot 2, then do continue, with no other calls. "
prompt += "Because the robot status is a dependency, and a call with an output. When you do continue, it will reprompt you again with the input, and all of the call response modules, this time including the status. You can then call led accordingly and end through io call"
prompt += "At the end of the message, if you require to do an action based on the output of a call, call io platform for the continue function: <call:{\"platform\": \"io\", \"function\": \"continue\", \"parameters\": []}>"

def extract_all_calls(input_str):
    matches = re.findall(r"<call:(\{.*?\})>", input_str)

    calls = []
    for m in matches:
        try:
            parsed = json.loads(m)
            calls.append(parsed)
        except json.JSONDecodeError as e:
            print(f"Failed to decode: {m}\nError: {e}")
            continue

    return calls

def handle_message(input, call_responses, output=""):
    try:
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": input}
        ]
        for i in call_responses:
            messages += [{"role": "assistant", "content": i}]
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        output += response["choices"][0]["message"]["content"] + "break"
        print(output)
        calls = extract_all_calls(response["choices"][0]["message"]["content"])

        for call in calls:
            if call['platform'] == "io" and call['function'] == "continue":
                return handle_message(input, call_responses, output)
            execution = "functions." + call['platform'] + "." + call['function'] + "("
            for parameter_index in range(0, len(call['parameters'])):
                parameter = call['parameters'][parameter_index]
                execution += parameter['name'] + "=" + "\"" + parameter['value'] + "\""
                if parameter_index != len(call['parameters']) - 1:
                    execution += ", "
            execution += ")"
            if json.loads(connectionsDoc)[call['platform']]['functions'][call['function']]['output'] == True:
                call_responses += ["Output from call: " + str(call) + " is the following: " + str(eval(execution))]
            else:
                exec(execution)

        return jsonify({"output": output})

    except Exception as e:
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
