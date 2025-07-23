"use client";

import { useState } from 'react';
import { uploadDocuments } from '@/services/api';
import { useUser } from '@/context/UserContext';
import toast from 'react-hot-toast';
import { Upload, Link as LinkIcon } from 'lucide-react';

const FileUploader = () => {
    const [urls, setUrls] = useState<string>('');
    const [files, setFiles] = useState<File[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const { userId } = useUser();

    const handleUpload = async () => {
        if (!userId) {
            toast.error('User not initialized.');
            return;
        }
        if (urls.trim().length === 0 && files.length === 0) {
            toast.error('Please provide at least one URL or file.');
            return;
        }

        setIsUploading(true);
        const toastId = toast.loading('Uploading documents...');

        const urlList = urls.split(',').map(url => url.trim()).filter(url => url);

        try {
            const response = await uploadDocuments(userId, urlList, files);
            toast.success(response.message, { id: toastId });
            setUrls('');
            setFiles([]);
        } catch (error) {
            toast.error('Failed to upload documents.', { id: toastId });
            console.error(error);
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="p-4 border-r border-gray-200 h-full">
            <h2 className="text-lg font-semibold mb-4 text-gray-800">Upload Sources</h2>
            <div className="space-y-4">
                <div>
                    <label htmlFor="urls" className="block text-sm font-medium text-gray-700 mb-1">
                        Web URLs (comma-separated)
                    </label>
                    <div className="relative">
                        <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
                        <input
                            type="text"
                            id="urls"
                            value={urls}
                            onChange={(e) => setUrls(e.target.value)}
                            placeholder="e.g., https://example.com"
                            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md shadow-sm"
                        />
                    </div>
                </div>
                <div>
                    <label htmlFor="files" className="block text-sm font-medium text-gray-700 mb-1">
                        Upload Files (PDF)
                    </label>
                    <input
                        type="file"
                        id="files"
                        multiple
                        accept=".pdf"
                        onChange={(e) => setFiles(Array.from(e.target.files || []))}
                        className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-600 hover:file:bg-indigo-100"
                    />
                </div>
                <button
                    onClick={handleUpload}
                    disabled={isUploading}
                    className="w-full bg-indigo-600 text-white py-2 px-4 rounded-md shadow-sm hover:bg-indigo-700 disabled:bg-indigo-300 flex items-center justify-center"
                >
                    <Upload className="h-5 w-5 mr-2" />
                    {isUploading ? 'Uploading...' : 'Upload'}
                </button>
            </div>
        </div>
    );
};

export default FileUploader;