"use client";

import { useState, useEffect, useRef } from 'react';
import ChatInput from './ChatInput';
import ChatMessage from './ChatMessage';
import { useUser } from '@/context/UserContext';
import { getHistory, postQuery } from '@/services/api';
import { ChatMessage as ChatMessageType } from '@/types';
import toast from 'react-hot-toast';
import { v4 as uuidv4 } from 'uuid';

const ChatWindow = () => {
    const [messages, setMessages] = useState<ChatMessageType[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const { userId, isLoading: isUserLoading } = useUser();
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(scrollToBottom, [messages]);

    useEffect(() => {
        if (userId) {
            const fetchHistory = async () => {
                try {
                    const history = await getHistory(userId);
                    const formattedHistory = history.flatMap(item => [
                        { ...item, isUserMessage: true },
                        { ...item, isUserMessage: false }
                    ]);
                    setMessages(formattedHistory);
                } catch (error) {
                    console.log("No history found for this user.");
                }
            };
            fetchHistory();
        }
    }, [userId]);

    const handleSendMessage = async (question: string) => {
        if (!userId) return;

        setIsLoading(true);
        const userMessage: ChatMessageType = {
            message_id: uuidv4(),
            user_id: userId,
            timestamp: new Date().toISOString(),
            question,
            answer: '',
            isUserMessage: true,
            search_performed: false
        };
        setMessages(prev => [...prev, userMessage]);

        try {
            const response = await postQuery(userId, question, true);
            const aiMessage: ChatMessageType = {
                ...response,
                user_id: userId,
                question: question,
                timestamp: new Date().toISOString(),
            };
            setMessages(prev => [...prev, aiMessage]);
        } catch (error) {
            toast.error('Failed to get a response from the assistant.');
            setMessages(prev => prev.slice(0, -1));
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-white">
            <div className="flex-1 overflow-y-auto">
                {(isUserLoading || isLoading) && messages.length === 0 && <div className="p-8 text-center text-gray-500">Loading Chat...</div>}
                {!isUserLoading && messages.length === 0 && (
                    <div className="p-8 text-center text-gray-500">Upload documents and ask a question to start the chat.</div>
                )}
                {messages.map((msg, index) => (
                    <ChatMessage key={`${msg.message_id}-${index}`} message={msg} />
                ))}
                <div ref={messagesEndRef} />
            </div>
            <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
        </div>
    );
};

export default ChatWindow;