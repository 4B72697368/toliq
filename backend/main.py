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
    system_prompt = f.read()

prompt = "Your role is to respond to the user and invocate a call from the list below like: <call:{\"name\": \"test\", \"parameters\": [{\"name\": \"duration\", \"value\": \"30\"}]}> ALL CALLS MUST BE INVOCATED IN THIS STRUCTURE, IF A CALL TYPE OR PARAMETER OF A CALL TYPE IS NOT MENTIONED IN THE DOC BELOW, DO NOT USE IT, ALL INVOCATIONS MUST COMPLY WITH THE FOLLOWING DOC:"
system_prompt = prompt + system_prompt

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

@app.route("/", methods=["POST"])
def handle_request():
    data = request.get_json()

    if not data or "input" not in data:
        return jsonify({"error": "Missing 'input' in JSON body"}), 400

    user_input = data["input"]

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        output = response["choices"][0]["message"]["content"]

        calls = extract_all_calls(output)

        for call in calls:
            execution = "functions." + call['name'] + "("
            for parameter_index in range(0, len(call['parameters'])):
                parameter = call['parameters'][parameter_index]
                execution += parameter['name'] + "=" + "\"" + parameter['value'] + "\""
                if parameter_index != len(call['parameters']) - 1:
                    execution += ", "
            execution += ")"
            exec(execution)

        return jsonify({"output": output})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
