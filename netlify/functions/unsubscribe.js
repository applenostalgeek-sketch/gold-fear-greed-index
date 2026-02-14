// Netlify Function: unsubscribe a contact from the alert list
exports.handler = async (event) => {
  const headers = {
    'Access-Control-Allow-Origin': 'https://onoff.markets',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Content-Type': 'application/json',
  };

  // Handle CORS preflight
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers };
  }

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers, body: JSON.stringify({ error: 'Method not allowed' }) };
  }

  try {
    const { email } = JSON.parse(event.body);

    if (!email || !email.includes('@')) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'Valid email required' }) };
    }

    const RESEND_API_KEY = process.env.RESEND_API_KEY;
    const AUDIENCE_ID = process.env.RESEND_AUDIENCE_ID;

    if (!RESEND_API_KEY || !AUDIENCE_ID) {
      return { statusCode: 500, headers, body: JSON.stringify({ error: 'Server configuration error' }) };
    }

    // Find contact by email first
    const searchResponse = await fetch(`https://api.resend.com/audiences/${AUDIENCE_ID}/contacts`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${RESEND_API_KEY}`,
      },
    });

    const contacts = await searchResponse.json();

    if (!searchResponse.ok) {
      return { statusCode: searchResponse.status, headers, body: JSON.stringify({ error: 'Failed to lookup contact' }) };
    }

    const contact = contacts.data?.find(c => c.email === email.toLowerCase().trim());

    if (!contact) {
      // Don't reveal if email exists or not — just say success
      return { statusCode: 200, headers, body: JSON.stringify({ success: true }) };
    }

    // Remove contact from audience
    const deleteResponse = await fetch(`https://api.resend.com/audiences/${AUDIENCE_ID}/contacts/${contact.id}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${RESEND_API_KEY}`,
      },
    });

    if (!deleteResponse.ok) {
      const err = await deleteResponse.json();
      return { statusCode: deleteResponse.status, headers, body: JSON.stringify({ error: err.message || 'Unsubscribe failed' }) };
    }

    return { statusCode: 200, headers, body: JSON.stringify({ success: true }) };

  } catch (err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'Server error' }) };
  }
};
