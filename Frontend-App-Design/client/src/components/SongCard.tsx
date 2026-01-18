import { Song } from "@shared/schema";
import { Play, Pause, Heart, Disc, Maximize2, Minimize2, Mic, Square, CheckCircle2, Loader2, Volume2, Send, Headphones } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useToggleFavorite, useUpdateProgress } from "@/hooks/use-songs";
import { useToast } from "@/hooks/use-toast";
import { JuicyButton } from "@/components/JuicyButton";

interface SongCardProps {
  song: Song & { videoUrl?: string | null; hasVideo?: boolean; previewUrl?: string | null; hasPreview?: boolean };
}

// Flask backend API base URL
const API_BASE = (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_URL) || "http://localhost:6767";

export function SongCard({ song }: SongCardProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [hasRecording, setHasRecording] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [isPlayingRecording, setIsPlayingRecording] = useState(false);
  const [recordedAudioBlob, setRecordedAudioBlob] = useState<Blob | null>(null);
  const [recordedAudioUrl, setRecordedAudioUrl] = useState<string | null>(null);
  const [score, setScore] = useState<{ 
    accuracy: number; 
    weighted_score: number; 
    avg_line_accuracy: number;
    worst_lines: Array<{ line: number; text: string; accuracy: number }>;
  } | null>(null);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isPlayingPreview, setIsPlayingPreview] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const previewAudioRef = useRef<HTMLAudioElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { mutate: toggleFavorite } = useToggleFavorite();
  const { mutate: updateProgress } = useUpdateProgress();
  const { toast } = useToast();
  const [currentProgress, setCurrentProgress] = useState(song.progress || 0);

  const handlePlayToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!song.videoUrl && !song.hasVideo) {
      return; // No video to play
    }
    
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
    }
    setIsPlaying(!isPlaying);
  };

  // Sync video element state with isPlaying
  useEffect(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.muted = false; // Unmute when playing
        videoRef.current.play().catch(err => {
          console.error('Error playing video:', err);
          setIsPlaying(false);
        });
      } else {
        videoRef.current.pause();
        videoRef.current.muted = true; // Mute when paused (preview mode)
        // Reset to first frame for preview
        videoRef.current.currentTime = 0.1;
      }
    }
  }, [isPlaying]);

  // Handle video end
  const handleVideoEnd = () => {
    setIsPlaying(false);
  };

  // Handle fullscreen toggle
  const handleFullscreen = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!videoRef.current) return;

    try {
      if (!document.fullscreenElement) {
        // Enter fullscreen
        if (videoRef.current.requestFullscreen) {
          await videoRef.current.requestFullscreen();
        } else if ((videoRef.current as any).webkitRequestFullscreen) {
          await (videoRef.current as any).webkitRequestFullscreen();
        } else if ((videoRef.current as any).mozRequestFullScreen) {
          await (videoRef.current as any).mozRequestFullScreen();
        } else if ((videoRef.current as any).msRequestFullscreen) {
          await (videoRef.current as any).msRequestFullscreen();
        }
      } else {
        // Exit fullscreen
        if (document.exitFullscreen) {
          await document.exitFullscreen();
        } else if ((document as any).webkitExitFullscreen) {
          await (document as any).webkitExitFullscreen();
        } else if ((document as any).mozCancelFullScreen) {
          await (document as any).mozCancelFullScreen();
        } else if ((document as any).msExitFullscreen) {
          await (document as any).msExitFullscreen();
        }
      }
    } catch (err) {
      console.error('Error toggling fullscreen:', err);
    }
  };

  // Handle double-click to fullscreen
  const handleDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (song.videoUrl && song.hasVideo && isPlaying) {
      handleFullscreen(e);
    }
  };

  // Listen for fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, []);

  const handleFavorite = (e: React.MouseEvent) => {
    e.stopPropagation();
    toggleFavorite(song.id);
  };

  // Recording functionality
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (isRecording) {
      interval = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } else {
      setRecordingTime(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isRecording]);

  const startRecording = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      const chunks: Blob[] = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };
      
      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        
        // Store blob for later upload
        setRecordedAudioBlob(blob);
        
        // Create URL for playback
        const audioUrl = URL.createObjectURL(blob);
        setRecordedAudioUrl(audioUrl);
        setHasRecording(true);
        
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
      };
      
      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
      
      // Start video playback when recording starts
      if (videoRef.current && (song.videoUrl || song.hasVideo)) {
        setIsPlaying(true);
        videoRef.current.muted = false;
        videoRef.current.play().catch(err => {
          console.error('Error playing video:', err);
        });
      }
    } catch (error) {
      console.error("Error starting recording:", error);
      toast({
        title: "Recording Error",
        description: "Could not access microphone. Please check permissions.",
        variant: "destructive",
      });
    }
  };

  const stopRecording = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
      setMediaRecorder(null);
    }
  };

  const togglePlayback = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (audioRef.current) {
      if (isPlayingRecording) {
        audioRef.current.pause();
        setIsPlayingRecording(false);
      } else {
        audioRef.current.play();
        setIsPlayingRecording(true);
      }
    }
  };

  const sendRecording = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!recordedAudioBlob) return;

    try {
      setAnalysisProgress(10);
      setIsAnalyzing(true);
      
      // Upload webm file directly - server will convert to WAV for processing
      const uploadFormData = new FormData();
      uploadFormData.append('audio', recordedAudioBlob, `song_${song.id}_recording_${Date.now()}.webm`);
      uploadFormData.append('song_id', song.id.toString());
      uploadFormData.append('song_title', song.title);
      uploadFormData.append('language', song.language || 'en-us');
      
      setAnalysisProgress(30);
      
      // Simulate progress updates
      const progressInterval = setInterval(() => {
        setAnalysisProgress((prev) => {
          if (prev < 90) return prev + 5;
          return prev;
        });
      }, 500);
      
      const compareResponse = await fetch(`${API_BASE}/api/songs/compare`, {
        method: 'POST',
        body: uploadFormData,
        credentials: 'include',
      });
      
      clearInterval(progressInterval);
      setAnalysisProgress(100);
      
      if (compareResponse.ok) {
        const result = await compareResponse.json();
        
        // Store score for display
        if (result.accuracy !== undefined) {
          const accuracyPercent = Math.round(result.accuracy * 100);
          
          setScore({
            accuracy: result.accuracy,
            weighted_score: result.weighted_score !== undefined ? result.weighted_score : result.accuracy,
            avg_line_accuracy: result.avg_line_accuracy !== undefined ? result.avg_line_accuracy : result.accuracy,
            worst_lines: result.worst_lines || []
          });
          
          // Update mastery progress with the accuracy score
          // Use the higher of current progress or new accuracy (don't decrease)
          const newProgress = Math.max(currentProgress, accuracyPercent);
          setCurrentProgress(newProgress);
          
          // Save to backend
          updateProgress({ 
            id: song.id, 
            progress: newProgress 
          });
        }
        
        const accuracyPercent = (result.accuracy * 100).toFixed(1);
        const weightedPercent = result.weighted_score ? (result.weighted_score * 100).toFixed(1) : null;
        
        toast({
          title: "Analysis Complete!",
          description: `Overall Accuracy: ${accuracyPercent}%${weightedPercent ? ` | Weighted: ${weightedPercent}%` : ''}`,
        });
      } else {
        const error = await compareResponse.json().catch(() => ({}));
        toast({
          title: "Error",
          description: error.message || "Failed to analyze recording.",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error("Error sending recording:", error);
      setIsAnalyzing(false);
      setAnalysisProgress(0);
      toast({
        title: "Error",
        description: "Failed to send recording. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsAnalyzing(false);
      setAnalysisProgress(0);
    }
  };

  // Sync progress with song prop when it updates
  useEffect(() => {
    if (song.progress !== undefined && song.progress !== null) {
      setCurrentProgress(song.progress);
    }
  }, [song.progress]);

  // Handle audio playback end
  useEffect(() => {
    const audio = audioRef.current;
    if (audio) {
      const handleEnded = () => {
        setIsPlayingRecording(false);
      };
      audio.addEventListener('ended', handleEnded);
      return () => {
        audio.removeEventListener('ended', handleEnded);
      };
    }
  }, [recordedAudioUrl]);

  // Progress Ring Calculation
  const radius = 24;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - ((song.progress || 0) / 100) * circumference;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -5 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className="bg-white rounded-3xl p-4 border-2 border-slate-100 shadow-[0_4px_0_0_rgba(241,245,249,1)] hover:shadow-[0_8px_0_0_rgba(241,245,249,1)] transition-all cursor-pointer group relative overflow-hidden"
    >
      {/* Video/Image Cover */}
      <div 
        ref={containerRef}
        className="relative aspect-square rounded-2xl overflow-hidden mb-4 bg-slate-100"
        onDoubleClick={handleDoubleClick}
      >
        {/* Video Preview/Player (shown when video is available) */}
        {song.videoUrl && song.hasVideo ? (
          <video
            ref={videoRef}
            src={`${API_BASE}${song.videoUrl}`}
            className={cn(
              "w-full h-full object-cover transition-opacity duration-300 absolute inset-0",
              isPlaying ? "opacity-100 z-0" : "opacity-100 z-0"
            )}
            onEnded={handleVideoEnd}
            onLoadedMetadata={(e) => {
              // Seek to first frame to show preview
              if (e.currentTarget && !isPlaying) {
                e.currentTarget.currentTime = 0.1;
                e.currentTarget.muted = true;
              }
            }}
            playsInline
            controls={false}
            muted={true}
            preload="metadata"
          />
        ) : (
          /* Cover Image (only shown when no video) */
          <img 
            src={song.coverUrl || ""} 
            alt={song.title}
            className="w-full h-full object-cover transition-all duration-700 absolute inset-0 opacity-100 z-0 group-hover:scale-110"
          />
        )}
        
        {/* Play/Pause Overlay Button */}
        <div className={cn(
          "absolute inset-0 bg-black/20 flex items-center justify-center transition-opacity duration-300 z-10",
          isPlaying ? "opacity-0 hover:opacity-100" : "opacity-0 group-hover:opacity-100"
        )}>
          <div className="flex items-center gap-3">
            <button 
              onClick={handlePlayToggle}
              disabled={!song.videoUrl && !song.hasVideo}
              className={cn(
                "w-14 h-14 bg-white rounded-full flex items-center justify-center shadow-lg transform transition-transform",
                (!song.videoUrl && !song.hasVideo) ? "opacity-50 cursor-not-allowed" : "hover:scale-110 active:scale-95"
              )}
            >
              {isPlaying ? (
                <Pause className="w-6 h-6 text-[#B878E8] fill-[#B878E8]" />
              ) : (
                <Play className="w-6 h-6 text-[#B878E8] fill-[#B878E8] ml-1" />
              )}
            </button>
            
            {/* Fullscreen Button (only show when video is playing) */}
            {song.videoUrl && song.hasVideo && isPlaying && (
              <button
                onClick={handleFullscreen}
                className="w-12 h-12 bg-white/90 rounded-full flex items-center justify-center shadow-lg transform transition-transform hover:scale-110 active:scale-95"
                title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
              >
                {isFullscreen ? (
                  <Minimize2 className="w-5 h-5 text-[#B878E8]" />
                ) : (
                  <Maximize2 className="w-5 h-5 text-[#B878E8]" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="space-y-1">
        <div className="flex justify-between items-start">
          <div className="flex-1 min-w-0">
            <h3 className="font-extrabold text-slate-700 text-lg leading-tight line-clamp-1" title={song.title}>
              {song.title}
            </h3>
            {song.artist && (
              <p className="text-slate-500 text-sm font-medium mt-0.5 line-clamp-1" title={song.artist}>
                {song.artist}
              </p>
            )}
          </div>
          <button 
            onClick={handleFavorite}
            className="text-slate-300 hover:text-red-400 transition-colors ml-2 flex-shrink-0"
          >
            <Heart className={cn("w-5 h-5", song.isFavorite && "fill-red-400 text-red-400")} />
          </button>
        </div>
        
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-slate-400 font-bold text-sm uppercase tracking-wide">
            {song.language}
          </p>
          {song.genre && (
            <>
              <span className="text-slate-300">•</span>
              <p className="text-slate-400 text-xs font-medium">
                {song.genre}
              </p>
            </>
          )}
          {song.hasPreview && song.previewUrl && (
            <>
              <span className="text-slate-300">•</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (previewAudioRef.current) {
                    if (isPlayingPreview) {
                      previewAudioRef.current.pause();
                      setIsPlayingPreview(false);
                    } else {
                      previewAudioRef.current.currentTime = 0;
                      previewAudioRef.current.play();
                      setIsPlayingPreview(true);
                    }
                  }
                }}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-all",
                  isPlayingPreview
                    ? "bg-purple-100 text-purple-700 hover:bg-purple-200"
                    : "bg-blue-100 text-blue-700 hover:bg-blue-200"
                )}
                title={isPlayingPreview ? "Stop preview" : "Play 10-second preview"}
              >
                {isPlayingPreview ? (
                  <>
                    <Square className="w-3 h-3" />
                    Stop
                  </>
                ) : (
                  <>
                    <Headphones className="w-3 h-3" />
                    Preview
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Progress Ring Overlay (Absolute Positioned Bottom Right) */}
      <div className="absolute bottom-4 right-4 w-8 h-8 hidden">
        {/* Keeping hidden for now as play button is central, but could be enabled for complex layouts */}
      </div>
      
      {/* Hidden audio element for preview */}
      {song.hasPreview && song.previewUrl && (
        <audio
          ref={previewAudioRef}
          src={`${API_BASE}${song.previewUrl}`}
          onEnded={() => setIsPlayingPreview(false)}
          onPause={() => setIsPlayingPreview(false)}
          className="hidden"
        />
      )}
      
      {/* Recording Button and Progress Bar */}
      <div className="mt-4 space-y-3">
        {/* Recording Button */}
        <div className="flex items-center gap-2">
          {isRecording ? (
            <JuicyButton
              onClick={stopRecording}
              variant="destructive"
              className="flex-1 text-sm py-2"
            >
              <Square className="w-4 h-4 mr-2" />
              Stop Recording ({Math.floor(recordingTime / 60)}:{(recordingTime % 60).toString().padStart(2, '0')})
            </JuicyButton>
          ) : isAnalyzing ? (
            <JuicyButton
              variant="secondary"
              className="flex-1 text-sm py-2"
              disabled
            >
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Analyzing...
            </JuicyButton>
          ) : (
            <div className="w-full space-y-2">
              <div className="flex items-center gap-2">
                <JuicyButton
                  onClick={startRecording}
                  variant="primary"
                  className="flex-1 text-sm py-2"
                >
                  <Mic className="w-4 h-4 mr-2" />
                  {hasRecording ? "Record Again" : "Record Your Singing"}
                </JuicyButton>
                {hasRecording && recordedAudioUrl && (
                  <button
                    onClick={togglePlayback}
                    className={cn(
                      "w-10 h-10 rounded-xl flex items-center justify-center transition-all",
                      isPlayingRecording 
                        ? "bg-red-100 text-red-500 hover:bg-red-200" 
                        : "bg-purple-100 text-[#B878E8] hover:bg-purple-200"
                    )}
                    title={isPlayingRecording ? "Pause playback" : "Play recording"}
                  >
                    {isPlayingRecording ? (
                      <Pause className="w-5 h-5" />
                    ) : (
                      <Volume2 className="w-5 h-5" />
                    )}
                  </button>
                )}
              </div>
              {hasRecording && recordedAudioUrl && !score && (
                <JuicyButton
                  onClick={sendRecording}
                  variant="success"
                  className="w-full text-sm py-2"
                  disabled={isAnalyzing}
                >
                  <Send className="w-4 h-4 mr-2" />
                  Send
                </JuicyButton>
              )}
            </div>
          )}
        </div>
        
        {/* Analysis Progress Bar */}
        {isAnalyzing && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500 font-medium">Analyzing pronunciation...</span>
              <span className="text-slate-600 font-bold">{analysisProgress}%</span>
            </div>
            <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${analysisProgress}%` }}
                transition={{ duration: 0.3, ease: "easeOut" }}
                className="h-full bg-gradient-to-r from-blue-500 to-[#B878E8] rounded-full"
              />
            </div>
          </div>
        )}
        
        {/* Hidden audio element for playback */}
        {recordedAudioUrl && (
          <audio
            ref={audioRef}
            src={recordedAudioUrl}
            preload="auto"
            className="hidden"
          />
        )}
        
        {/* Score Display */}
        {score && !isAnalyzing && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-2xl p-4 border-2 border-purple-200 space-y-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-600 uppercase tracking-wide">Accuracy Score</span>
              <span className="text-lg font-black text-purple-600">
                {(score.accuracy * 100).toFixed(1)}%
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Overall Accuracy</span>
                <span className="font-bold text-slate-700">{(score.accuracy * 100).toFixed(1)}%</span>
              </div>
              {score.weighted_score && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Weighted Score</span>
                  <span className="font-bold text-slate-700">{(score.weighted_score * 100).toFixed(1)}%</span>
                </div>
              )}
              {score.avg_line_accuracy && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Avg Line Accuracy</span>
                  <span className="font-bold text-slate-700">{(score.avg_line_accuracy * 100).toFixed(1)}%</span>
                </div>
              )}
            </div>
            {/* Progress bar */}
            <div className="mt-3 h-2 w-full bg-slate-200 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${score.accuracy * 100}%` }}
                transition={{ duration: 1, ease: "easeOut" }}
                className={cn(
                  "h-full rounded-full",
                  score.accuracy >= 0.8 ? "bg-[#B878E8]" : score.accuracy >= 0.6 ? "bg-yellow-500" : "bg-red-500"
                )}
              />
            </div>
            
            {/* Top 3 Worst Lines */}
            {score.worst_lines && score.worst_lines.length > 0 && (
              <div className="mt-4 pt-4 border-t-2 border-slate-200">
                <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wide mb-3">
                  Lines to Practice (Lowest Accuracy)
                </h4>
                <div className="space-y-2">
                  {score.worst_lines.slice(0, 3).map((line, idx) => (
                    <div
                      key={idx}
                      className="bg-white rounded-xl p-3 border-2 border-red-100"
                    >
                      <div className="flex items-start justify-between mb-1">
                        <span className="text-xs font-bold text-red-500">Line {line.line}</span>
                        <span className="text-xs font-bold text-slate-600">
                          {(line.accuracy * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="text-sm text-slate-700 font-medium">{line.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
        
        {/* Learning Progress Bar */}
        <div>
          <div className="flex justify-between text-xs font-bold text-slate-400 mb-1">
            <span>Mastery</span>
            <span>{currentProgress}%</span>
          </div>
          <div className="h-3 w-full bg-slate-100 rounded-full overflow-hidden">
            <motion.div 
              initial={{ width: 0 }}
              animate={{ width: `${currentProgress}%` }}
              transition={{ duration: 1, ease: "easeOut" }}
              className={cn(
                "h-full rounded-full",
                currentProgress === 100 ? "bg-yellow-400" : "bg-[#B878E8]"
              )}
            />
          </div>
        </div>
      </div>
    </motion.div>
  );
}
