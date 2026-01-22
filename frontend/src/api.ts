import axios from 'axios';

// Use the environment variable if available, otherwise fallback to localhost
const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
console.log("Using Backend URL:", API_URL);

export const uploadFile = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await axios.post(`${API_URL}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
};

export const extractData = async (filename: string, selection: any) => {
  const formData = new FormData();
  formData.append('filename', filename);
  formData.append('selection', JSON.stringify(selection));
  const response = await axios.post(`${API_URL}/extract`, formData);
  return response.data;
};

export const checkExistence = async (data: any[], tableName: string) => {
  const formData = new FormData();
  formData.append('data', JSON.stringify(data));
  formData.append('table_name', tableName);
  const response = await axios.post(`${API_URL}/check-existence`, formData);
  return response.data;
};

export const saveData = async (data: any[], tableName: string) => {
  const formData = new FormData();
  formData.append('data', JSON.stringify(data));
  formData.append('table_name', tableName);
  const response = await axios.post(`${API_URL}/save`, formData);
  return response.data;
};

export const exportData = async (data: any[], tableName: string) => {
  const formData = new FormData();
  formData.append('data', JSON.stringify(data));
  formData.append('table_name', tableName);
  const response = await axios.post(`${API_URL}/export`, formData, {
    responseType: 'blob'
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `${tableName}.csv`);
  document.body.appendChild(link);
  link.click();
};

export const exportDataAsPdf = async (data: any[], tableName: string) => {
  const formData = new FormData();
  formData.append('data', JSON.stringify(data));
  formData.append('table_name', tableName);
  const response = await axios.post(`${API_URL}/export-pdf`, formData, {
    responseType: 'blob'
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `${tableName}_report.pdf`);
  document.body.appendChild(link);
  link.click();
};

export const downloadTemplate = async (tableName: string) => {
  const formData = new FormData();
  formData.append('table_name', tableName);
  const response = await axios.post(`${API_URL}/generate-template`, formData, {
    responseType: 'blob'
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `${tableName}_template.pdf`);
  document.body.appendChild(link);
  link.click();
};