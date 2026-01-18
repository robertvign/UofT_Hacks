import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";

// Flask backend API – must be running: cd src && python server.py (default http://localhost:6767)
const API_BASE = (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_URL) || "http://localhost:6767";

export interface Conversation {
  question: string;
  response: string;
  target_word: string;
  error_rate: number;
  count: number;
}

export interface Lesson {
  conversations: Conversation[];
  generated_at?: string;
  language?: string;
}

export function useLessons() {
  const { toast } = useToast();
  
  return useQuery({
    queryKey: ['lessons'],
    queryFn: async (): Promise<Lesson | null> => {
      try {
        const response = await fetch(`${API_BASE}/api/lessons`, {
          credentials: 'include',
        });
        
        if (response.ok) {
          const data = await response.json();
          if (data.lessons && data.lessons.conversations) {
            return data.lessons;
          }
          return null;
        } else if (response.status === 404) {
          // No lessons yet, that's okay
          return null;
        } else {
          throw new Error('Failed to fetch lessons');
        }
      } catch (error) {
        console.error("Error fetching lessons:", error);
        return null;
      }
    },
    retry: false,
  });
}

export function useGenerateLessons() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  
  return useMutation({
    mutationFn: async ({ language, num_conversations }: { language?: string; num_conversations?: number }) => {
      const response = await fetch(`${API_BASE}/api/lessons/generate`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          language: language || 'fr-fr',
          num_conversations: num_conversations || 3,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || "Failed to generate lessons");
      }

      const data = await response.json();
      return data.lessons as Lesson;
    },
    onSuccess: (lessons) => {
      // Update the cache with new lessons
      queryClient.setQueryData(['lessons'], lessons);
      
      toast({
        title: "Lessons Generated!",
        description: "Your personalized lessons are ready to practice.",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message || "Failed to generate lessons. Please try again.",
        variant: "destructive",
      });
    },
  });
}

export function useSavePracticeRecording() {
  const { toast } = useToast();
  
  return useMutation({
    mutationFn: async ({ audioBlob, conversationIndex }: { audioBlob: Blob; conversationIndex: number }) => {
      const formData = new FormData();
      formData.append('audio', audioBlob, `practice_${conversationIndex}_${Date.now()}.webm`);
      formData.append('conversation_index', conversationIndex.toString());
      
      const response = await fetch(`${API_BASE}/api/lessons/practice`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || "Failed to save recording");
      }
      
      return await response.json();
    },
    onSuccess: () => {
      toast({
        title: "Recording Saved!",
        description: "Your practice has been saved and will be analyzed.",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message || "Failed to save recording. Please try again.",
        variant: "destructive",
      });
    },
  });
}

