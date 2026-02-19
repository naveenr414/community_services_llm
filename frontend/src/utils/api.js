// src/utils/api.js - Centralized API utility
import { API_URL } from '../config';

/**
 * Makes an authenticated API call with JWT token
 * @param {string} endpoint - API endpoint (e.g., '/outreach_list/')
 * @param {object} options - Fetch options (method, body, etc.)
 * @returns {Promise<Response>} - Response object
 */
export const authenticatedFetch = async (endpoint, options = {}) => {
  const token = localStorage.getItem('accessToken');
  
  if (!token) {
    // Redirect to login if no token
    window.location.href = '/login';
    throw new Error('No authentication token found');
  }

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    ...options.headers,
  };

  // FIX: Changed from fetch`...` to fetch(...)
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized - token expired or invalid
  if (response.status === 401) {    
    // Clear invalid token and all session data
    localStorage.removeItem('accessToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('username');
    localStorage.removeItem('organization');
    localStorage.removeItem('loginTimestamp');
    
    // Redirect to login
    window.location.href = '/login';
    throw new Error('Session expired. Please login again.');
  }

  return response;
};

/**
 * Convenience wrapper for GET requests
 * @param {string} endpoint - API endpoint
 * @returns {Promise<any>} - Parsed JSON response
 */
export const apiGet = async (endpoint) => {
  const response = await authenticatedFetch(endpoint, { method: 'GET' });
  return response.json();
};

/**
 * Convenience wrapper for POST requests
 * @param {string} endpoint - API endpoint
 * @param {object} data - Request body data
 * @returns {Promise<any>} - Parsed JSON response
 */
export const apiPost = async (endpoint, data) => {
  const response = await authenticatedFetch(endpoint, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  return response.json();
};

/**
 * Convenience wrapper for PUT requests
 * @param {string} endpoint - API endpoint
 * @param {object} data - Request body data
 * @returns {Promise<any>} - Parsed JSON response
 */
export const apiPut = async (endpoint, data) => {
  const response = await authenticatedFetch(endpoint, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  return response.json();
};

/**
 * Convenience wrapper for DELETE requests
 * @param {string} endpoint - API endpoint
 * @returns {Promise<any>} - Parsed JSON response
 */
export const apiDelete = async (endpoint) => {
  const response = await authenticatedFetch(endpoint, {
    method: 'DELETE',
  });
  return response.json();
};