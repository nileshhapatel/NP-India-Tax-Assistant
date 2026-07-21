// API client for frontend
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const fetcher = (url) => {
  // If URL starts with /, prepend the API base URL
  const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
  return fetch(fullUrl).then((res) => {
    if (!res.ok) {
      throw new Error(`API Error: ${res.status}`);
    }
    return res.json();
  });
};

export const apiCall = async (method, path, body = null) => {
  const fullUrl = path.startsWith('http') ? path : `${API_BASE_URL}${path}`;
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
  };
  if (body) {
    options.body = JSON.stringify(body);
  }
  const res = await fetch(fullUrl, options);
  if (!res.ok) {
    throw new Error(`API Error: ${res.status}`);
  }
  return res.json();
};
