// GET endpoint for retrieving calendar data
function doGet(e) {
	Logger.log('GET Request received:', e);
	
	const action = e.parameter.action || 'listEvents';
	const start = e.parameter.start;
	const end = e.parameter.end;
	
	switch (action) {
		case 'listEvents':
			return handleListEvents({ start, end });
		default:
			return jsonResponse({ error: 'Unknown action' });
	}
}

// POST endpoint for calendar operations
function doPost(e) {
	Logger.log('Received POST request:', e.postData?.contents);
	
	try {
		const payload = JSON.parse(e.postData.contents);
		const action = payload.action;
		const data = payload.data;
		
		switch (action) {
			case 'createEvents':
				return handleCreateEvents(data);
			case 'updateEvent':
				return handleUpdateEvent(data);
			case 'deleteEvent':
				return handleDeleteEvent(data);
			default:
				return jsonResponse({ error: 'Unknown action' });
		}
	} catch (error) {
		return jsonResponse({ error: 'Invalid request: ' + error.message });
	}
}

// Response helper
function jsonResponse(data) {
	return ContentService.createTextOutput(JSON.stringify(data, null, 2))
		.setMimeType(ContentService.MimeType.JSON);
}

// Calendar operation handlers
function handleListEvents(data) {
	try {
		const calendar = CalendarApp.getDefaultCalendar();
		const startDate = data.start ? new Date(data.start) : new Date();
		const endDate = data.end ? new Date(data.end) : new Date(startDate.getTime() + 7 * 24 * 60 * 60 * 1000);
		
		const events = calendar.getEvents(startDate, endDate);
		const eventList = events.map(event => ({
			id: event.getId(),
			title: event.getTitle(),
			start: event.getStartTime().toISOString(),
			end: event.getEndTime().toISOString(),
			description: event.getDescription()
		}));
		
		return jsonResponse({
			success: true,
			events: eventList
		});
	} catch (error) {
		return jsonResponse({ error: 'Failed to list events: ' + error.message });
	}
}

function handleCreateEvents(data) {
	if (!Array.isArray(data.events)) {
		return jsonResponse({ error: 'Events array is required' });
	}
	
	try {
		const calendar = CalendarApp.getDefaultCalendar();
		const createdEvents = [];
		const errors = [];
		
		for (const eventData of data.events) {
			if (!eventData.title || !eventData.start || !eventData.end) {
				errors.push({
					event: eventData,
					error: 'Missing required fields (title, start, end)'
				});
				continue;
			}
			
			try {
				const event = calendar.createEvent(
					eventData.title,
					new Date(eventData.start),
					new Date(eventData.end),
					{ description: eventData.description }
				);
				
				createdEvents.push({
					id: event.getId(),
					title: event.getTitle(),
					start: event.getStartTime().toISOString(),
					end: event.getEndTime().toISOString(),
					description: event.getDescription()
				});
			} catch (eventError) {
				errors.push({
					event: eventData,
					error: eventError.message
				});
			}
		}
		
		return jsonResponse({
			success: true,
			created: createdEvents,
			errors: errors
		});
	} catch (error) {
		return jsonResponse({ error: 'Failed to create events: ' + error.message });
	}
}

function handleUpdateEvent(data) {
	if (!data.id) {
		return jsonResponse({ error: 'Event ID is required' });
	}
	
	try {
		const calendar = CalendarApp.getDefaultCalendar();
		const event = calendar.getEventById(data.id);
		
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
				description: event.getDescription()
			}
		});
	} catch (error) {
		return jsonResponse({ error: 'Failed to update event: ' + error.message });
	}
}

function handleDeleteEvent(data) {
	if (!data.id) {
		return jsonResponse({ error: 'Event ID is required' });
	}
	
	try {
		const calendar = CalendarApp.getDefaultCalendar();
		const event = calendar.getEventById(data.id);
		
		if (!event) {
			return jsonResponse({ error: 'Event not found' });
		}
		
		event.deleteEvent();
		return jsonResponse({ success: true });
	} catch (error) {
		return jsonResponse({ error: 'Failed to delete event: ' + error.message });
	}
}

// Simple test function
function testCalendarOperations() {
	Logger.log('Starting calendar operations test...');
	
	// Test 1: List events
	Logger.log('\nTest 1: List events');
	const listTest = doGet({
		parameter: {
			action: 'listEvents',
			start: '2024-03-21',
			end: '2024-03-28'
		}
	});
	Logger.log('List events response: ' + listTest.getContent());
	
	// Test 2: Create multiple events
	Logger.log('\nTest 2: Create events');
	const createTest = doPost({
		postData: {
			contents: JSON.stringify({
				action: 'createEvents',
				data: {
					events: [
						{
							title: 'Test Event 1',
							start: '2024-03-22T10:00:00Z',
							end: '2024-03-22T11:00:00Z',
							description: 'First test event'
						},
						{
							title: 'Test Event 2',
							start: '2024-03-22T14:00:00Z',
							end: '2024-03-22T15:00:00Z',
							description: 'Second test event'
						}
					]
				}
			})
		}
	});
	Logger.log('Create events response: ' + createTest.getContent());
	
	return 'Tests completed';
}