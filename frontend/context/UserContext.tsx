"use client";

import React, { createContext, useState, useContext, ReactNode, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { createUser } from '@/services/api';
import toast from 'react-hot-toast';

interface UserContextType {
  userId: string | null;
  isLoading: boolean;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export const UserProvider = ({ children }: { children: ReactNode }) => {
  const [userId, setUserId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initializeUser = async () => {
      let currentUserId = localStorage.getItem('userId');
      if (!currentUserId) {
        currentUserId = uuidv4();
        try {
          await createUser(currentUserId);
          localStorage.setItem('userId', currentUserId);
          toast.success("New user session created!");
        } catch (error) {
          toast.error("Failed to create a user session. Please refresh.");
          console.error(error);
          setIsLoading(false);
          return;
        }
      }
      setUserId(currentUserId);
      setIsLoading(false);
    };

    initializeUser();
  }, []);

  return (
    <UserContext.Provider value={{ userId, isLoading }}>
      {children}
    </UserContext.Provider>
  );
};

export const useUser = () => {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
};