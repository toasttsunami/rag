import axios from 'axios';
import { ChatMessage, QueryResponse } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

const apiClient = axios.create({
  baseURL: API_URL,
});

export const createUser = async (userId: string): Promise<{ user_id: string }> => {
  const response = await apiClient.post('/users/create', null, { params: { user_id: userId } });
  return response.data;
};

export const uploadDocuments = async (userId: string, urls: string[], files: File[]): Promise<{ message: string }> => {
  const formData = new FormData();
  formData.append('user_id', userId);
  
  urls.forEach(url => {
    formData.append('urls', url);
  });

  files.forEach(file => {
    formData.append('files', file);
  });

  const response = await apiClient.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const postQuery = async (userId: string, question: string, includeSources: boolean): Promise<QueryResponse> => {
    const response = await apiClient.post('/query', {
        user_id: userId,
        question: question,
        include_sources: includeSources,
    });
    return response.data;
};

export const getHistory = async (userId: string): Promise<ChatMessage[]> => {
    const response = await apiClient.get(`/users/${userId}/history`);
    return response.data;
};