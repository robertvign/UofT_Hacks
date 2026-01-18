import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect } from "react";

// Flask backend API base URL
const API_BASE = (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_URL) || "http://localhost:6767";

interface User {
  username: string;
  likes: number[];
  mastery: Record<string, number>;
}

interface AuthResponse {
  status: string;
  user?: User;
  message?: string;
  error?: string;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check if user is logged in on mount
  const { data: currentUser, refetch: refetchUser } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/api/auth/me`, {
        credentials: 'include', // Important for cookies/sessions
      });
      if (!response.ok) {
        return null;
      }
      const data: AuthResponse = await response.json();
      return data.user || null;
    },
    retry: false,
  });

  useEffect(() => {
    if (currentUser !== undefined) {
      setUser(currentUser);
      setIsLoading(false);
    }
  }, [currentUser]);

  const loginMutation = useMutation({
    mutationFn: async ({ username, password }: { username: string; password: string }) => {
      try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ username, password }),
        });
        
        if (!response.ok) {
          const error = await response.json().catch(() => ({}));
          throw new Error((error as any).message || (error as any).error || 'Login failed');
        }
        
        const data: AuthResponse = await response.json();
        return data.user!;
      } catch (error: any) {
        // Handle network errors
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
          throw new Error(`Cannot connect to server at ${API_BASE}. Make sure the Flask server is running on port 6767.`);
        }
        throw error;
      }
    },
    onSuccess: (userData) => {
      setUser(userData);
      refetchUser();
    },
  });

  const queryClient = useQueryClient();
  
  const logoutMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
      return response.ok;
    },
    onSuccess: () => {
      setUser(null);
      // Clear all queries on logout
      queryClient.clear();
    },
  });

  return {
    user,
    isLoading,
    isAuthenticated: !!user,
    login: loginMutation.mutate,
    logout: () => logoutMutation.mutate(),
    isLoggingIn: loginMutation.isPending,
    isLoggingOut: logoutMutation.isPending,
    loginError: loginMutation.error,
  };
}

