import requests
import json


class functions:
    class test_platform:
        @staticmethod
        def led(duration, color="FF0000"):
            print("LED of color: " + color + " for the duration: " + duration)

    class gsheets:
        ENDPOINT = "https://script.google.com/macros/s/AKfycbySvv3CNPXA9s-eKHooAEj5OkQl-70Zv_lMwYtDtoUGe7hd3dyVSMNacuXV2nDuE-trNA/exec"

        @staticmethod
        def list_sheets():
            """Get list of all sheets in the document"""
            try:
                response = requests.get(
                    functions.gsheets.ENDPOINT, params={"action": "listSheets"}
                )
                return response.json()
            except Exception as e:
                return {"error": f"Failed to list sheets: {str(e)}"}

        @staticmethod
        def read_sheet(sheet_name=""):
            """Read content of a specific sheet"""
            try:
                params = {"action": "readSheet"}
                if sheet_name:
                    params["sheetName"] = sheet_name
                response = requests.get(functions.gsheets.ENDPOINT, params=params)
                return response.json()
            except Exception as e:
                return {"error": f"Failed to read sheet: {str(e)}"}

        @staticmethod
        def write_cells(cells):
            """Write values/formulas to specific cells

            Args:
                cells: JSON string of cell updates in format:
                    {
                        "A1": {"value": "Test"},
                        "B1": {"formula": "=SUM(C1:D1)"}
                    }
            """
            try:
                payload = {
                    "action": "writeCells",
                    "data": {
                        "cells": json.loads(cells) if isinstance(cells, str) else cells
                    },
                }
                response = requests.post(functions.gsheets.ENDPOINT, json=payload)
                return response.json()
            except Exception as e:
                return {"error": f"Failed to write cells: {str(e)}"}
