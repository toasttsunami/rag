"use client";

import { useUser } from '@/context/UserContext';
import { LoaderCircle } from 'lucide-react';

const Header = () => {
    const { userId, isLoading } = useUser();

    return (
        <header className="bg-gray-800 text-white p-4 flex justify-between items-center shadow-md z-10">
            <h1 className="text-xl font-bold">Research Helper</h1>
            <div className="text-sm">
                {isLoading ? (
                    <div className="flex items-center gap-2">
                        <LoaderCircle className="animate-spin" />
                        <span>Initializing...</span>
                    </div>
                ) : (
                    <span className="font-mono bg-gray-700 px-2 py-1 rounded">User ID: {userId}</span>
                )}
            </div>
        </header>
    );
};

export default Header;