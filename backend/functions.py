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
                # Handle both direct JSON objects and JSON strings
                cells_data = cells
                if isinstance(cells, str):
                    try:
                        cells_data = json.loads(cells)
                    except json.JSONDecodeError as e:
                        return {"error": f"Invalid cells format: {str(e)}"}

                payload = {
                    "action": "writeCells",
                    "data": {"cells": cells_data},
                }
                response = requests.post(user["gsheetsEndpoint"], json=payload)
                return response.json()
            except Exception as e:
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
                    dt = tz.localize(dt)
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
                    functions.calendar._format_datetime(start)
                    if start
                    else functions.calendar._format_datetime()
                )

                if end:
                    end_dt = functions.calendar._format_datetime(end, is_end=True)
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
                        event.get("start")
                    )
                    processed_event["end"] = functions.calendar._format_datetime(
                        event.get("end"), is_end=True
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
                    data["start"] = functions.calendar._format_datetime(start)
                if end:
                    data["end"] = functions.calendar._format_datetime(end, is_end=True)
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
