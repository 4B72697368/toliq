import requests
import json
from datetime import datetime, timedelta
import pytz
import os
import platform


class functions:
    # Get system timezone or default to UTC
    @staticmethod
    def get_system_timezone():
        try:
            # Try to get system timezone from tzlocal
            from tzlocal import get_localzone

            return get_localzone()
        except ImportError:
            try:
                # Fallback to getting from time module
                import time

                return pytz.timezone(time.tzname[time.daylight])
            except:
                # Last resort fallback to UTC
                return pytz.timezone("UTC")

    class datetime:
        @staticmethod
        def get_current_time():
            """Get the current date and time in ISO format with timezone information"""
            try:
                tz = functions.get_system_timezone()
                current_time = datetime.now(tz)
                utc_time = current_time.astimezone(pytz.UTC)

                # Calculate offset from UTC in hours
                offset_hours = current_time.utcoffset().total_seconds() / 3600
                offset_sign = "+" if offset_hours >= 0 else ""

                # Create example timestamps for demonstration
                example_local = current_time.replace(hour=14, minute=0)  # 2:00 PM local
                example_utc = example_local.astimezone(pytz.UTC)  # Convert to UTC

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
                response = requests.post(functions.gsheets.ENDPOINT, json=payload)
                return response.json()
            except Exception as e:
                return {"error": f"Failed to write cells: {str(e)}"}

    class calendar:
        ENDPOINT = "https://script.google.com/macros/s/AKfycbyll3En1_atkFg6dS3gFb7TFDTMFKYsXZSRV8SBq2TNP2rSvtWgCu-aLFYgKzKGEpr7/exec"

        @staticmethod
        def _format_datetime(dt_str=None, is_end=False):
            """Helper to format datetime with timezone awareness
            If no datetime provided, uses current time for start, or current time + 1 hour for end
            Always adds 7 hours to convert PDT to UTC
            """
            if dt_str:
                # If only date provided, add default time
                if "T" not in dt_str:
                    dt_str = f"{dt_str}T{'23:59:59' if is_end else '00:00:00'}"
                # Parse the datetime and add 7 hours for UTC
                dt = datetime.fromisoformat(dt_str.replace("Z", ""))
            else:
                # Use current time
                dt = datetime.now()
                if is_end:
                    # For end time with no input, add 1 hour to current time
                    dt += timedelta(hours=1)

            # Add 7 hours to convert PDT to UTC
            dt += timedelta(hours=7)
            return dt.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )  # Return in UTC format with Z suffix

        @staticmethod
        def list_events(start=None, end=None):
            """List calendar events within a date range
            If no dates provided, lists events from now to 7 days ahead"""
            try:
                # Format start date/time
                start_dt = (
                    functions.calendar._format_datetime(start)
                    if start
                    else functions.calendar._format_datetime()
                )

                # Format end date/time
                if end:
                    end_dt = functions.calendar._format_datetime(end, is_end=True)
                else:
                    # Default to 7 days from start if no end date provided
                    tz = functions.get_system_timezone()
                    end_dt = (
                        datetime.fromisoformat(start_dt) + timedelta(days=7)
                    ).isoformat()

                params = {"action": "listEvents", "start": start_dt, "end": end_dt}
                response = requests.get(functions.calendar.ENDPOINT, params=params)
                return response.json()
            except Exception as e:
                return {"error": f"Failed to list events: {str(e)}"}

        @staticmethod
        def create_events(events):
            """Create multiple calendar events
            Automatically handles timezone conversion for event times"""
            try:
                # Process each event's datetime fields
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
                response = requests.post(functions.calendar.ENDPOINT, json=payload)
                return response.json()
            except Exception as e:
                return {"error": f"Failed to create events: {str(e)}"}

        @staticmethod
        def update_event(id, title=None, start=None, end=None, description=None):
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
                response = requests.post(functions.calendar.ENDPOINT, json=payload)
                return response.json()
            except Exception as e:
                return {"error": f"Failed to update event: {str(e)}"}

        @staticmethod
        def delete_event(id):
            """Delete a calendar event"""
            try:
                payload = {"action": "deleteEvent", "data": {"id": id}}
                response = requests.post(functions.calendar.ENDPOINT, json=payload)
                return response.json()
            except Exception as e:
                return {"error": f"Failed to delete event: {str(e)}"}
