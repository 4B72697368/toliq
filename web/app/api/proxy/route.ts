import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    console.log('🔄 [Proxy API] Forwarding request to Flask server');
    console.log('📦 Request body preview:', JSON.stringify(body).substring(0, 100) + '...');

    // Check if user endpoints are configured
    if (!body.user || (!body.user.calendarEndpoint && !body.user.gsheetsEndpoint)) {
      console.warn('⚠️ [Proxy API] No endpoints configured in user settings');
    }

    const flaskResponse = await fetch('http://localhost:5001/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!flaskResponse.ok) {
      const errorText = await flaskResponse.text();
      console.error(`❌ [Proxy API] Flask server error ${flaskResponse.status}: ${errorText}`);
      
      return NextResponse.json(
        { 
          error: `Flask server error: ${flaskResponse.status}`,
          details: errorText
        }, 
        { status: flaskResponse.status }
      );
    }

    // Check if we got a valid JSON response
    const contentType = flaskResponse.headers.get('Content-Type');
    if (!contentType || !contentType.includes('application/json')) {
      const text = await flaskResponse.text();
      console.error('❌ [Proxy API] Non-JSON response from Flask server:', text.substring(0, 200));
      return NextResponse.json(
        { error: 'Invalid response type from server', details: text.substring(0, 500) },
        { status: 500 }
      );
    }

    const data = await flaskResponse.json();
    console.log('✅ [Proxy API] Received response from Flask server');
    return NextResponse.json(data);
  } catch (error) {
    console.error('[Proxy API] Error:', error);
    return NextResponse.json(
      { 
        error: 'Internal server error', 
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
} 