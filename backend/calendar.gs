
// GET endpoint for retrieving calendar resources
function doGet(e) {
	Logger.log('GET Request received:', e);
	// Verify authorization
	const authHeader = e.parameter.authorization || '';
	if (!verifyAuth(authHeader)) {
		return jsonResponse({
			error: 'Unauthorized',
			debug: {
				receivedAuth: authHeader,
				expectedAuth: SHARED_SECRET,
				parameters: e.parameter,
				headers: e.headers || {},
			},
		});
	}

	const action = e.parameter.action || 'listEvents';
	const start = e.parameter.start;
	const end = e.parameter.end;

	switch (action) {
		case 'listEvents':
			return handleListEvents({ start, end });
		case 'getEvent':
			const eventId = e.parameter.eventId;
			if (!eventId) {
				return jsonResponse({ error: 'Event ID is required' });
			}
			return handleGetEvent(eventId);
		default:
			return jsonResponse({ error: 'Unknown action' });
	}
}

// POST endpoint for calendar operations
function doPost(e) {
	Logger.log('Received POST request:');
	Logger.log('Post data: ' + JSON.stringify(e.postData));
	Logger.log('Raw contents: ' + (e.postData?.contents || 'no contents'));

	try {
		const payload = JSON.parse(e.postData.contents);
		Logger.log('Parsed payload: ' + JSON.stringify(payload));

		// Check authorization from the request body
		if (!verifyAuth(payload.authorization)) {
			return jsonResponse({
				error: 'Unauthorized',
				debug: {
					receivedAuth: payload.authorization,
					expectedAuth: SHARED_SECRET,
					rawContents: e.postData?.contents,
				},
			});
		}

		const action = payload.action;
		const data = payload.data;

		Logger.log('Action: ' + action);
		Logger.log('Data: ' + JSON.stringify(data));

		switch (action) {
			case 'createEvent':
				return handleCreateEvent(data);
			case 'updateEvent':
				return handleUpdateEvent(data);
			case 'deleteEvent':
				return handleDeleteEvent(data);
			case 'listEvents':
				return handleListEvents(data);
			default:
				Logger.log('Unknown action: ' + action);
				return jsonResponse({ error: 'Unknown action' });
		}
	} catch (error) {
		Logger.log('Error processing request: ' + error.toString());
		Logger.log('Stack trace: ' + error.stack);
		return jsonResponse({ error: 'Invalid request: ' + error.message });
	}
}

// Authorization helper
function verifyAuth(authHeader) {
	return authHeader === SHARED_SECRET;
}

// Response helper
function jsonResponse(data) {
	Logger.log('Sending response: ' + JSON.stringify(data));
	return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}

// Calendar operation handlers
function handleCreateEvent(data) {
	if (!data.title || !data.start || !data.end) {
		return jsonResponse({ error: 'Missing required fields' });
	}

	try {
		const calendar = CalendarApp.getDefaultCalendar();
		const event = calendar.createEvent(data.title, new Date(data.start), new Date(data.end), { description: data.description });

		return jsonResponse({
			success: true,
			event: {
				id: event.getId(),
				title: event.getTitle(),
				start: event.getStartTime().toISOString(),
				end: event.getEndTime().toISOString(),
				description: event.getDescription(),
			},
		});
	} catch (error) {
		return jsonResponse({ error: 'Failed to create event: ' + error.message });
	}
}

function handleUpdateEvent(data) {
	if (!data.eventId) {
		return jsonResponse({ error: 'Event ID is required' });
	}

	try {
		const calendar = CalendarApp.getDefaultCalendar();
		const event = calendar.getEventById(data.eventId);

		if (!event) {
			return jsonResponse({ error: 'Event not found' });
		}

		if (data.title) event.setTitle(data.title);
		if (data.start) event.setStartTime(new Date(data.start));
		if (data.end) event.setEndTime(new Date(data.end));
		if (data.description) event.setDescription(data.description);

		return jsonResponse({
			success: true,
			event: {
				id: event.getId(),
				title: event.getTitle(),
				start: event.getStartTime().toISOString(),
				end: event.getEndTime().toISOString(),
				description: event.getDescription(),
			},
		});
	} catch (error) {
		return jsonResponse({ error: 'Failed to update event: ' + error.message });
	}
}

function handleDeleteEvent(data) {
	if (!data.eventId) {
		return jsonResponse({ error: 'Event ID is required' });
	}

	try {
		const calendar = CalendarApp.getDefaultCalendar();
		const event = calendar.getEventById(data.eventId);

		if (!event) {
			return jsonResponse({ error: 'Event not found' });
		}

		event.deleteEvent();
		return jsonResponse({ success: true });
	} catch (error) {
		return jsonResponse({ error: 'Failed to delete event: ' + error.message });
	}
}

function handleGetEvent(eventId) {
	try {
		const calendar = CalendarApp.getDefaultCalendar();
		const event = calendar.getEventById(eventId);

		if (!event) {
			return jsonResponse({ error: 'Event not found' });
		}

		return jsonResponse({
			event: {
				id: event.getId(),
				title: event.getTitle(),
				start: event.getStartTime().toISOString(),
				end: event.getEndTime().toISOString(),
				description: event.getDescription(),
			},
		});
	} catch (error) {
		return jsonResponse({ error: 'Failed to get event: ' + error.message });
	}
}

function handleListEvents(data) {
	try {
		Logger.log('Handling list events with data: ' + JSON.stringify(data));
		const calendar = CalendarApp.getDefaultCalendar();
		const startDate = data.start ? new Date(data.start) : new Date();
		const endDate = data.end ? new Date(data.end) : new Date(startDate.getTime() + 7 * 24 * 60 * 60 * 1000);

		Logger.log('Date range: ' + startDate + ' to ' + endDate);

		const events = calendar.getEvents(startDate, endDate);
		Logger.log('Found ' + events.length + ' events');

		const eventList = events.map((event) => ({
			id: event.getId(),
			title: event.getTitle(),
			start: event.getStartTime().toISOString(),
			end: event.getEndTime().toISOString(),
			description: event.getDescription(),
		}));

		Logger.log('Returning events: ' + JSON.stringify(eventList));
		return jsonResponse({ events: eventList });
	} catch (error) {
		Logger.log('Error listing events: ' + error.toString());
		Logger.log('Stack trace: ' + error.stack);
		return jsonResponse({ error: 'Failed to list events: ' + error.message });
	}
}

function testDoGet() {
	Logger.log('Starting test of doGet...');

	// Simulate a GET request event object
	const testEvent = {
		parameter: {
			action: 'listEvents',
			start: '2024-03-21',
			end: '2026-03-28',
			authorization: SHARED_SECRET, // Add the authorization header
		},
	};

	Logger.log('Test event object: ' + JSON.stringify(testEvent));

	// Call doGet with our test event
	const response = doGet(testEvent);

	Logger.log('Response received: ' + JSON.stringify(response.getContent()));

	return response;
}