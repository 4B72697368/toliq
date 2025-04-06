import requests
import json
from datetime import datetime, timedelta
import pytz
from tzlocal import get_localzone


class functions:
    class datetime:
        @staticmethod
        def get_current_time(user):
            """Get the current date and time in ISO format with timezone information"""
            try:
                tz = get_localzone()
                current_time = datetime.now(tz)
                utc_time = current_time.astimezone(pytz.UTC)

                offset_hours = current_time.utcoffset().total_seconds() / 3600
                offset_sign = "+" if offset_hours >= 0 else ""

                example_local = current_time.replace(hour=14, minute=0)
                example_utc = example_local.astimezone(pytz.UTC)

                return {
                    "current": {
                        "datetime": current_time.isoformat(),
                        "timezone": str(tz),
                        "friendly": current_time.strftime(
                            "%A, %B %d, %Y at %I:%M:%S %p %Z"
                        ),
                    },
                    "utc": {
                        "datetime": utc_time.isoformat(),
                        "friendly": utc_time.strftime("%I:%M:%S %p UTC"),
                    },
                    "context": (
                        f"Current time is {current_time.strftime('%I:%M %p')} {tz} ({offset_sign}{offset_hours:g} hours from UTC). "
                    ),
                    "timestamp": int(current_time.timestamp()),
                }
            except Exception as e:
                return {"error": f"Failed to get current time: {str(e)}"}

    class gsheets:
        @staticmethod
        def list_sheets(user):
            """Get list of all sheets in the document"""
            try:
                response = requests.get(
                    user["gsheetsEndpoint"], params={"action": "listSheets"}
                )
                return response.json()
            except Exception as e:
                return {"error": f"Failed to list sheets: {str(e)}"}

        @staticmethod
        def read_sheet(user, sheet_name=""):
            """Read content of a specific sheet"""
            try:
                # Check if required endpoint exists
                if (
                    not user
                    or "gsheetsEndpoint" not in user
                    or not user["gsheetsEndpoint"]
                ):
                    return {
                        "error": "Google Sheets endpoint not configured in user settings"
                    }

                params = {"action": "readSheet"}
                if sheet_name:
                    params["sheetName"] = sheet_name

                print(
                    f"Sending request to Google Sheets endpoint: {user['gsheetsEndpoint'][:30]}... with params: {params}"
                )
                response = requests.get(user["gsheetsEndpoint"], params=params)

                # Print the response status and first part of content for debugging
                print(f"Google Sheets API response status: {response.status_code}")
                response_preview = (
                    response.text[:100] if response.text else "Empty response"
                )
                print(f"Response preview: {response_preview}")

                # Try parsing the response as JSON
                try:
                    return response.json()
                except Exception as json_error:
                    return {
                        "error": f"Failed to parse Google Sheets API response as JSON: {str(json_error)}"
                    }
            except Exception as e:
                import traceback

                error_trace = traceback.format_exc()
                print(f"Error in read_sheet: {str(e)}")
                print(f"Traceback: {error_trace}")
                return {"error": f"Failed to read sheet: {str(e)}"}

        @staticmethod
        def write_cells(user, cells):
            """Write values/formulas to specific cells

            Args:
                cells: Cell updates in format:
                    {
                        "A1": {"value": "Test"},
                        "B1": {"formula": "=SUM(C1:D1)"}
                    }
                    Can be provided as either a JSON string or a direct object.
            """
            try:
                print(f"=== write_cells called with cells type: {type(cells)}")
                if isinstance(cells, str):
                    print(
                        f"=== Cells provided as string, first 100 chars: {cells[:100]}"
                    )
                else:
                    print(
                        f"=== Cells provided as object, keys: {list(cells.keys())[:5] if cells else 'empty'}"
                    )

                # Check if endpoint exists
                if (
                    not user
                    or "gsheetsEndpoint" not in user
                    or not user["gsheetsEndpoint"]
                ):
                    return {
                        "error": "Google Sheets endpoint not configured in user settings"
                    }

                # Handle both direct JSON objects and JSON strings
                cells_data = cells
                if isinstance(cells, str):
                    try:
                        # First try normal parsing
                        try:
                            cells_data = json.loads(cells)
                            print(f"=== Successfully parsed cells JSON normally")
                        except json.JSONDecodeError as e:
                            print(f"=== Standard JSON parsing failed: {str(e)}")

                            # Try with additional unescaping for double-escaped quotes
                            fixed_cells = cells.replace('\\"', '"').replace(
                                '\\\\"', '\\"'
                            )
                            try:
                                cells_data = json.loads(fixed_cells)
                                print(
                                    f"=== Successfully parsed cells JSON after fixing escapes"
                                )
                            except json.JSONDecodeError as e2:
                                print(f"=== Fixed JSON parsing also failed: {str(e2)}")
                                print(f"=== Original: {cells[:50]}...")
                                print(f"=== Fixed attempt: {fixed_cells[:50]}...")

                                # If the string starts with a quote and ends with a quote, try removing them
                                if cells.startswith('"') and cells.endswith('"'):
                                    try:
                                        inner_content = cells[1:-1].replace('\\"', '"')
                                        cells_data = json.loads(inner_content)
                                        print(
                                            f"=== Successfully parsed cells JSON after removing outer quotes"
                                        )
                                    except json.JSONDecodeError as e3:
                                        # Give up and report the original error
                                        raise e
                                else:
                                    # Give up and report the original error
                                    raise e
                    except json.JSONDecodeError as e:
                        error_context = cells[
                            max(0, int(e.pos) - 30) : min(len(cells), int(e.pos) + 30)
                        ]
                        return {
                            "error": f"Invalid cells format: {str(e)}",
                            "details": f"Error near: ...{error_context}... (position {e.pos})",
                            "tip": "Make sure your JSON is valid and doesn't contain improperly escaped quotes",
                        }

                # Verify that the cells data is a dictionary
                if not isinstance(cells_data, dict):
                    return {
                        "error": "Invalid cells format: Must be a dictionary/object",
                        "received": f"Type: {type(cells_data).__name__}",
                    }

                # Check for any cells with improperly structured formulas
                for cell, data in cells_data.items():
                    if not isinstance(data, dict):
                        return {
                            "error": f"Invalid format for cell {cell}: Value must be an object with 'value' or 'formula' key",
                            "received": f"Type: {type(data).__name__}",
                        }
                    if "formula" in data and not isinstance(data["formula"], str):
                        return {
                            "error": f"Invalid formula for cell {cell}: Formula must be a string",
                            "received": f"Type: {type(data['formula']).__name__}",
                        }

                print(f"=== Sending writeCells request with {len(cells_data)} cells")
                payload = {
                    "action": "writeCells",
                    "data": {"cells": cells_data},
                }
                response = requests.post(user["gsheetsEndpoint"], json=payload)

                # Check for a successful status code
                if response.status_code != 200:
                    return {
                        "error": f"Failed to write cells: HTTP {response.status_code}",
                        "details": response.text,
                    }

                # Try to parse the response
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {
                        "error": "Failed to parse response from Google Sheets",
                        "details": response.text[:200],
                    }

            except Exception as e:
                import traceback

                error_trace = traceback.format_exc()
                print(f"=== Error in write_cells: {str(e)}")
                print(f"=== Traceback: {error_trace}")
                return {"error": f"Failed to write cells: {str(e)}"}

    class calendar:
        @staticmethod
        def _format_datetime(user, dt_str=None, is_end=False):
            """Helper to format datetime with timezone awareness
            If no datetime provided, uses current time for start, or current time + 1 hour for end
            Always adds 7 hours to convert PDT to UTC
            """
            tz = get_localzone()

            if dt_str:
                if "T" not in dt_str:
                    dt_str = f"{dt_str}T{'23:59:59' if is_end else '00:00:00'}"
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                    # Replace localize() with a more compatible approach
                    naive_dt = dt.replace(tzinfo=None)
                    dt = datetime.combine(naive_dt.date(), naive_dt.time(), tzinfo=tz)
            else:
                dt = datetime.now(tz)
                if is_end:
                    dt += timedelta(hours=1)

            utc_dt = dt.astimezone(pytz.UTC)
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        @staticmethod
        def list_events(user, start=None, end=None):
            """List calendar events within a date range
            If no dates provided, lists events from now to 7 days ahead"""
            try:
                start_dt = (
                    functions.calendar._format_datetime(user, start)
                    if start
                    else functions.calendar._format_datetime(user)
                )

                if end:
                    end_dt = functions.calendar._format_datetime(user, end, is_end=True)
                else:
                    tz = get_localzone()
                    end_dt = (
                        datetime.fromisoformat(start_dt) + timedelta(days=7)
                    ).isoformat()

                params = {"action": "listEvents", "start": start_dt, "end": end_dt}
                response = requests.get(user["calendarEndpoint"], params=params)
                return response.json()
            except Exception as e:
                return {"error": f"Failed to list events: {str(e)}"}

        @staticmethod
        def create_events(user, events):
            """Create multiple calendar events
            Automatically handles timezone conversion for event times"""
            try:
                processed_events = []
                for event in json.loads(events) if isinstance(events, str) else events:
                    processed_event = event.copy()
                    processed_event["start"] = functions.calendar._format_datetime(
                        user, event.get("start")
                    )
                    processed_event["end"] = functions.calendar._format_datetime(
                        user, event.get("end"), is_end=True
                    )
                    processed_events.append(processed_event)

                payload = {
                    "action": "createEvents",
                    "data": {"events": processed_events},
                }

                response = requests.post(user["calendarEndpoint"], json=payload)

                # Check for a successful status code
                if response.status_code != 200:
                    return {
                        "error": f"Failed to create events: HTTP {response.status_code}, {response.text}"
                    }

                # Attempt to parse the response as JSON
                try:
                    response_data = response.json()
                    return response_data
                except ValueError:
                    return {
                        "error": f"Failed to parse response as JSON: {response.text}"
                    }

            except Exception as e:
                return {"error": f"Failed to create events: {str(e)}"}

        @staticmethod
        def update_event(user, id, title=None, start=None, end=None, description=None):
            """Update a calendar event
            Automatically handles timezone conversion for event times"""
            try:
                data = {"id": id}
                if title:
                    data["title"] = title
                if start:
                    data["start"] = functions.calendar._format_datetime(user, start)
                if end:
                    data["end"] = functions.calendar._format_datetime(
                        user, end, is_end=True
                    )
                if description:
                    data["description"] = description

                payload = {"action": "updateEvent", "data": data}
                response = requests.post(user["calendarEndpoint"], json=payload)
                return response.json()
            except Exception as e:
                return {"error": f"Failed to update event: {str(e)}"}

        @staticmethod
        def delete_event(user, id):
            """Delete a calendar event"""
            try:
                payload = {"action": "deleteEvent", "data": {"id": id}}
                response = requests.post(user["calendarEndpoint"], json=payload)
                return response.json()
            except Exception as e:
                return {"error": f"Failed to delete event: {str(e)}"}
