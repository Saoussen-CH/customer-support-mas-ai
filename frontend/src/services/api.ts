import axios from 'axios';
import type {
  ChatResponse,
  ChatRequest,
  SessionListResponse,
  MessageHistoryResponse,
  ApiError
} from '../types';

// For development: http://localhost:8000
// For production (Cloud Run): uses relative URLs (served from same origin)
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Helper to get auth headers
function getAuthHeaders(): Record<string, string> {
  const user = localStorage.getItem('user');
  const token = localStorage.getItem('token');

  if (!user) {
    throw new Error('No user found. Please login or create anonymous user.');
  }

  const userData = JSON.parse(user);
  const headers: Record<string, string> = {};

  if (token && !userData.is_anonymous) {
    // Authenticated user
    headers['Authorization'] = `Bearer ${token}`;
  } else {
    // Anonymous user
    headers['X-User-Id'] = userData.user_id;
  }

  return headers;
}

// =============================================================================
// CHAT SERVICE
// =============================================================================

export const chatService = {
  async sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
    try {
      const headers = getAuthHeaders();

      console.log('[API] Sending message:', {
        message: message.substring(0, 50),
        session_id: sessionId
      });

      const requestData: ChatRequest = {
        message,
        session_id: sessionId,
      };

      const response = await apiClient.post<ChatResponse>('/api/chat', requestData, {
        headers,
      });

      console.log('[API] Received response:', {
        session_id: response.data.session_id,
        user_id: response.data.user_id
      });

      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        const apiError = error.response.data as any;
        throw new Error(apiError.error || apiError.detail || 'Failed to send message');
      }
      throw new Error('Network error occurred');
    }
  },

  async healthCheck(): Promise<boolean> {
    try {
      const response = await apiClient.get('/health');
      return response.status === 200;
    } catch {
      return false;
    }
  },
};

// =============================================================================
// SESSION SERVICE
// =============================================================================

export const sessionService = {
  async listSessions(): Promise<SessionListResponse> {
    try {
      const headers = getAuthHeaders();
      const response = await apiClient.get<SessionListResponse>('/api/sessions', {
        headers,
      });
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        const apiError = error.response.data as ApiError;
        throw new Error(apiError.error || 'Failed to load sessions');
      }
      throw new Error('Network error occurred');
    }
  },

  async renameSession(sessionId: string, newName: string): Promise<void> {
    try {
      const headers = getAuthHeaders();
      await apiClient.put(
        `/api/sessions/${sessionId}/rename`,
        { session_name: newName },
        { headers }
      );
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        const apiError = error.response.data as ApiError;
        throw new Error(apiError.error || 'Failed to rename session');
      }
      throw new Error('Network error occurred');
    }
  },

  async deleteSession(sessionId: string): Promise<void> {
    try {
      const headers = getAuthHeaders();
      await apiClient.delete(`/api/sessions/${sessionId}`, { headers });
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        const apiError = error.response.data as ApiError;
        throw new Error(apiError.error || 'Failed to delete session');
      }
      throw new Error('Network error occurred');
    }
  },

  async getSessionMessages(sessionId: string): Promise<MessageHistoryResponse> {
    try {
      const headers = getAuthHeaders();
      const response = await apiClient.get<MessageHistoryResponse>(
        `/api/sessions/${sessionId}/messages`,
        { headers }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        const apiError = error.response.data as ApiError;
        throw new Error(apiError.error || 'Failed to load messages');
      }
      throw new Error('Network error occurred');
    }
  },
};
