import { NextRequest, NextResponse } from 'next/server';

// Tell Next.js this route can accept requests from any origin
export const config = {
  runtime: 'edge',
};

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    console.log('🔄 [API Route] Forwarding request to Flask server:', body);

    const flaskResponse = await fetch('http://localhost:5000/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!flaskResponse.ok) {
      const errorText = await flaskResponse.text();
      console.error(`❌ [API Route] Flask server error: ${flaskResponse.status} - ${errorText}`);
      return NextResponse.json(
        { error: `Flask server error: ${flaskResponse.status}` }, 
        { status: flaskResponse.status }
      );
    }

    const data = await flaskResponse.json();
    console.log('✅ [API Route] Received response from Flask server');
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('❌ [API Route] Error handling request:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
} 