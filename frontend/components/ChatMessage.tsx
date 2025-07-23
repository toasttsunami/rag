"use client";

import { Bot, User, Globe } from 'lucide-react';
import { ChatMessage as ChatMessageType } from "@/types"

const ChatMessage = ({ message }: { message: ChatMessageType }) => {
  const isUser = message.isUserMessage;

  return (
    <div className={`flex items-start gap-4 p-4 ${isUser ? '' : 'bg-gray-50'}`}>
      <div className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center text-white ${isUser ? 'bg-blue-500' : 'bg-green-500'}`}>
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>
      <div className="flex-1">
        <p className="text-gray-800 whitespace-pre-wrap">{isUser ? message.question : message.answer}</p>
        {!isUser && message.search_performed && (
          <div className="flex items-center text-sm text-gray-500 mt-2">
            <Globe size={14} className="mr-1" />
            <span>Searched the web to generate this response.</span>
          </div>
        )}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2">
            <h3 className="text-xs font-semibold text-gray-600">Sources:</h3>
            <ul className="list-disc list-inside text-xs text-gray-500">
              {message.sources.filter(s => s !== 'Unknown').map((source, index) => (
                <li key={index} className="truncate" title={source}>{source}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;