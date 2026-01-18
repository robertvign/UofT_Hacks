import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { type Song, type InsertSong } from "@shared/schema";
import { api } from "@shared/routes";
import { useToast } from "@/hooks/use-toast";

// MOCK DATA - As requested in implementation notes
const MOCK_SONGS: Song[] = [
  {
    id: 1,
    title: "Wadaya",
    language: "Cherokee",
    region: "North America",
    coverUrl: "https://images.unsplash.com/photo-1519681393784-d120267933ba?w=800&q=80",
    progress: 75,
    isFavorite: true,
  },
  {
    id: 2,
    title: "Tūtira Mai Ngā Iwi",
    language: "Māori",
    region: "New Zealand",
    coverUrl: "https://images.unsplash.com/photo-1506057213367-028a17ec52e5?w=800&q=80",
    progress: 30,
    isFavorite: false,
  },
  {
    id: 3,
    title: "Oró Sé do Bheatha 'Bhaile",
    language: "Irish (Gaeilge)",
    region: "Ireland",
    coverUrl: "https://images.unsplash.com/photo-1590050752117-238cb0fb12b1?w=800&q=80",
    progress: 10,
    isFavorite: false,
  },
  {
    id: 4,
    title: "Valicha",
    language: "Quechua",
    region: "Andes",
    coverUrl: "https://images.unsplash.com/photo-1587595431973-160d0d94add1?w=800&q=80",
    progress: 90,
    isFavorite: true,
  },
  {
    id: 5,
    title: "Giiwedin",
    language: "Anishinaabemowin",
    region: "Great Lakes",
    coverUrl: "https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=800&q=80",
    progress: 0,
    isFavorite: false,
  },
  {
    id: 6,
    title: "Nje Mogu",
    language: "Bambara",
    region: "West Africa",
    coverUrl: "https://images.unsplash.com/photo-1516026672322-bc52d61a55d5?w=800&q=80",
    progress: 45,
    isFavorite: false,
  }
];

// Helper to simulate API delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Flask backend API – must be running: cd src && python server.py (default http://localhost:6767)
const API_BASE = (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_URL) || "http://localhost:6767";

// ============================================
// HOOKS
// ============================================

export function useSongs() {
  return useQuery({
    queryKey: [api.songs.list.path],
    queryFn: async () => {
      try {
        // Fetch from real API
        const response = await fetch(`${API_BASE}/api/songs`, {
          credentials: 'include', // Important for sessions
        });
        if (!response.ok) {
          throw new Error('Failed to fetch songs');
        }
        const data = await response.json();
        // Transform API response to match Song type
        return (data.songs || []).map((song: any) => {
          // Parse song name to extract title and artist if format is "Artist - Song"
          let title = song.title || song.song_name || 'Unknown';
          let artist = song.artist || null;
          
          // If title contains " - " and no artist is provided, split it
          if (!artist && title.includes(' - ')) {
            const parts = title.split(' - ', 2);
            artist = parts[0].trim();
            title = parts[1].trim() || title;
          }
          
          return {
            id: song.id,
            title: title,
            artist: artist,
            language: song.language || song.translation_language || 'Unknown',
            genre: song.genre || null,
            coverUrl: song.coverUrl || "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800&q=80",
            progress: song.progress !== undefined && song.progress !== null ? song.progress : 0,
            isFavorite: song.isFavorite || false,
            videoUrl: song.video_url || null,
            hasVideo: song.has_video || false,
            previewUrl: song.preview_url || null,
            hasPreview: song.has_preview || false,
          };
        });
      } catch (error) {
        console.error('Error fetching songs:', error);
        // Fallback to mock data if API fails
        await delay(800);
        return MOCK_SONGS;
      }
    },
  });
}

export function useCreateSong() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: async (data: InsertSong & { file?: File; youtubeUrl?: string }) => {
      // If file or YouTube URL is provided, upload to the new API endpoint
      if (data.file || data.youtubeUrl) {
        const formData = new FormData();
        if (data.file) {
          formData.append('file', data.file);
        }
        if (data.youtubeUrl) {
          formData.append('youtube_url', data.youtubeUrl);
        }
        // Send full title (will be parsed on backend if needed)
        formData.append('song_name', data.title);
        formData.append('artist', data.artist || '');
        formData.append('translation_language', data.language || '');
        formData.append('genre', data.genre || '');
        
        const response = await fetch(`${API_BASE}/api/upload`, {
          method: 'POST',
          body: formData,
          credentials: 'include', // Important for sessions
        });
        
        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error((err as any).message || (err as any).error || 'Failed to upload song');
        }
        
        const result = await response.json();
        const songData = result.song;
        
        // Parse song name to extract title and artist
        let title = songData.song_name || data.title || 'Unknown';
        let artist = data.artist || null;
        
        // If title contains " - " and no artist is provided, split it
        if (!artist && title.includes(' - ')) {
          const parts = title.split(' - ', 2);
          artist = parts[0].trim();
          title = parts[1].trim() || title;
        }
        
        // Transform to Song type (progress starts at 0% for all users)
        return {
          id: songData.id,
          title: title,
          artist: artist,
          language: songData.translation_language || data.language,
          genre: data.genre || null,
          coverUrl: data.coverUrl || "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800&q=80",
          progress: 0, // Always start at 0% mastery
          isFavorite: false,
        };
      }
      
      // Fallback for non-file uploads (old behavior)
      await delay(1500); 
      
      const newSong: Song = {
        ...data,
        id: Math.floor(Math.random() * 10000) + 10,
        progress: 0,
        isFavorite: false,
        coverUrl: data.coverUrl || "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800&q=80",
        region: data.region || "Unknown",
      };
      
      return newSong;
    },
    onSuccess: (newSong) => {
      // Invalidate and refetch songs list
      queryClient.invalidateQueries({ queryKey: [api.songs.list.path] });
      
      toast({
        title: "Song Uploaded!",
        description: "Song has been saved to the database successfully!",
        className: "bg-green-500 text-white border-none shadow-xl",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Could not upload song. Please try again.",
        variant: "destructive",
      });
    }
  });
}

export function useToggleFavorite() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (songId: number) => {
      // Get current favorite state
      const currentData = queryClient.getQueryData<Song[]>([api.songs.list.path]);
      const currentSong = currentData?.find(s => s.id === songId);
      const isCurrentlyLiked = currentSong?.isFavorite || false;
      
      // Update on backend
      const response = await fetch(`${API_BASE}/api/auth/preferences/likes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          song_id: songId,
          is_liked: !isCurrentlyLiked,
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to update favorite');
      }
      
      return songId;
    },
    onSuccess: (songId) => {
      // Invalidate to refetch with updated data from server
      queryClient.invalidateQueries({ queryKey: [api.songs.list.path] });
    }
  });
}

// Update mastery progress and save to backend
export function useUpdateProgress() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, progress }: { id: number, progress: number }) => {
      // Save to backend
      const response = await fetch(`${API_BASE}/api/auth/preferences/mastery`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          song_id: id,
          progress: progress,
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to update mastery progress');
      }
      
      return { id, progress };
    },
    onSuccess: () => {
      // Invalidate to refetch with updated data from server
      queryClient.invalidateQueries({ queryKey: [api.songs.list.path] });
    }
  });
}
