import React from "react";
import { Navigation } from "@/components/Navigation";
import { JuicyButton } from "@/components/JuicyButton";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { insertSongSchema, type InsertSong } from "@shared/schema";
import { useCreateSong } from "@/hooks/use-songs";
import { useToast } from "@/hooks/use-toast";
import { 
  Form, 
  FormControl, 
  FormField, 
  FormItem, 
  FormLabel, 
  FormMessage 
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Upload as UploadIcon, FileAudio, CheckCircle2, Link as LinkIcon, Youtube, Mic, Square } from "lucide-react";
import { motion } from "framer-motion";
import { useLocation } from "wouter";

export default function Upload() {
  const [, setLocation] = useLocation();
  const { mutate: createSong, isPending } = useCreateSong();
  const { toast } = useToast();
  
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = React.useState("");
  const [uploadMethod, setUploadMethod] = React.useState<"file" | "youtube" | "record">("file");
  const [isRecording, setIsRecording] = React.useState(false);
  const [mediaRecorder, setMediaRecorder] = React.useState<MediaRecorder | null>(null);
  const [recordedChunks, setRecordedChunks] = React.useState<Blob[]>([]);
  const [recordingTime, setRecordingTime] = React.useState(0);

  const form = useForm<InsertSong>({
    resolver: zodResolver(insertSongSchema),
    defaultValues: {
      title: "",
      artist: "",
      language: "",
      genre: "",
      coverUrl: "",
      isFavorite: false,
      progress: 0,
    }
  });

  // Recording functionality
  React.useEffect(() => {
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

  const startRecording = async () => {
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
        setRecordedChunks(chunks);
        
        // Convert to MP3 using backend endpoint
        try {
          const formData = new FormData();
          formData.append('audio', blob, `recording_${Date.now()}.webm`);
          
          const API_BASE = (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_URL) || "http://localhost:6767";
          const response = await fetch(`${API_BASE}/api/recordings/convert`, {
            method: 'POST',
            body: formData,
            credentials: 'include',
          });
          
          if (response.ok) {
            // Response is the MP3 file directly
            const mp3Blob = await response.blob();
            const contentDisposition = response.headers.get('content-disposition');
            let filename = `recording_${Date.now()}.mp3`;
            if (contentDisposition) {
              const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
              if (filenameMatch) {
                filename = filenameMatch[1];
              }
            }
            const audioFile = new File([mp3Blob], filename, { type: 'audio/mpeg' });
            setSelectedFile(audioFile);
            setUploadMethod("file");
            toast({
              title: "Recording Saved!",
              description: "Your recording has been converted to MP3 and is ready to upload.",
            });
          } else {
            // Fallback: use original webm file if conversion fails
            const audioFile = new File([blob], `recording_${Date.now()}.webm`, { type: 'audio/webm' });
            setSelectedFile(audioFile);
            setUploadMethod("file");
            toast({
              title: "Recording Saved",
              description: "Recording saved (conversion to MP3 may not be available).",
            });
          }
        } catch (error) {
          console.error("Error converting recording:", error);
          // Fallback: use original webm file
          const audioFile = new File([blob], `recording_${Date.now()}.webm`, { type: 'audio/webm' });
          setSelectedFile(audioFile);
          setUploadMethod("file");
          toast({
            title: "Recording Saved",
            description: "Recording saved locally. You can upload it as-is.",
          });
        }
        
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
      };
      
      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
      setRecordedChunks([]);
    } catch (error) {
      console.error("Error starting recording:", error);
      toast({
        title: "Recording Error",
        description: "Could not access microphone. Please check permissions.",
        variant: "destructive",
      });
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
      setMediaRecorder(null);
    }
  };

  function onSubmit(data: InsertSong) {
    if (uploadMethod === "file" && !selectedFile) {
      toast({
        title: "No file selected",
        description: "Please select an audio file to upload",
        variant: "destructive",
      });
      return;
    }
    
    if (uploadMethod === "youtube" && !youtubeUrl.trim()) {
      toast({
        title: "No YouTube URL",
        description: "Please enter a YouTube URL",
        variant: "destructive",
      });
      return;
    }

    createSong({ 
      ...data, 
      file: uploadMethod === "file" ? selectedFile : undefined,
      youtubeUrl: uploadMethod === "youtube" ? youtubeUrl.trim() : undefined
    }, {
      onSuccess: () => {
        // Form is reset in mutation success if needed, but we can also redirect
        setTimeout(() => setLocation("/"), 2000); // Redirect after short delay to show success state
      }
    });
  }

  return (
    <div className="min-h-screen bg-white pb-24 md:pb-10">
      <Navigation />
      
      <main className="max-w-xl mx-auto px-4 py-8">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-black text-slate-700 mb-2">Upload Song</h1>
          <p className="text-slate-400 font-medium">
            Share a song with the community.
          </p>
        </div>

        <div className="bg-white rounded-3xl border-2 border-slate-100 p-6 md:p-8 shadow-sm">
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="uppercase text-xs font-bold text-slate-400 tracking-wider ml-1">Title</FormLabel>
                    <FormControl>
                      <Input 
                        placeholder="e.g. Wadaya" 
                        {...field} 
                        className="rounded-xl border-2 border-slate-200 bg-slate-50 h-12 focus:border-blue-400 focus:ring-0 text-lg font-bold text-slate-700 placeholder:font-normal placeholder:text-slate-300 transition-colors"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="artist"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="uppercase text-xs font-bold text-slate-400 tracking-wider ml-1">Artist</FormLabel>
                    <FormControl>
                      <Input 
                        placeholder="e.g. The Weeknd" 
                        {...field}
                        className="rounded-xl border-2 border-slate-200 bg-slate-50 h-12 focus:border-blue-400 focus:ring-0 text-lg font-bold text-slate-700 placeholder:font-normal placeholder:text-slate-300 transition-colors"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <FormField
                  control={form.control}
                  name="language"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="uppercase text-xs font-bold text-slate-400 tracking-wider ml-1">Language</FormLabel>
                      <FormControl>
                        <Input 
                          placeholder="e.g. Cherokee" 
                          {...field}
                          className="rounded-xl border-2 border-slate-200 bg-slate-50 h-12 focus:border-blue-400 focus:ring-0 font-bold text-slate-700"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="genre"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="uppercase text-xs font-bold text-slate-400 tracking-wider ml-1">Genre (Optional)</FormLabel>
                      <FormControl>
                        <Input 
                          placeholder="e.g. Pop, Rock, Folk" 
                          value={field.value || ""} 
                          onChange={field.onChange}
                          className="rounded-xl border-2 border-slate-200 bg-slate-50 h-12 focus:border-blue-400 focus:ring-0 font-bold text-slate-700"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Upload Method Toggle */}
              <div className="pt-2">
                <FormLabel className="uppercase text-xs font-bold text-slate-400 tracking-wider ml-1 mb-3 block">Upload Method</FormLabel>
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <button
                    type="button"
                    onClick={() => {
                      setUploadMethod("file");
                      setYoutubeUrl("");
                    }}
                    className={`p-4 rounded-xl border-2 transition-all ${
                      uploadMethod === "file"
                        ? "border-blue-400 bg-blue-50"
                        : "border-slate-200 bg-slate-50 hover:border-slate-300"
                    }`}
                  >
                    <FileAudio className={`w-6 h-6 mx-auto mb-2 ${
                      uploadMethod === "file" ? "text-blue-500" : "text-slate-400"
                    }`} />
                    <p className={`text-sm font-bold ${
                      uploadMethod === "file" ? "text-blue-600" : "text-slate-500"
                    }`}>Upload File</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setUploadMethod("youtube");
                      setSelectedFile(null);
                    }}
                    className={`p-4 rounded-xl border-2 transition-all ${
                      uploadMethod === "youtube"
                        ? "border-red-400 bg-red-50"
                        : "border-slate-200 bg-slate-50 hover:border-slate-300"
                    }`}
                  >
                    <Youtube className={`w-6 h-6 mx-auto mb-2 ${
                      uploadMethod === "youtube" ? "text-red-500" : "text-slate-400"
                    }`} />
                    <p className={`text-sm font-bold ${
                      uploadMethod === "youtube" ? "text-red-600" : "text-slate-500"
                    }`}>YouTube URL</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (isRecording) {
                        stopRecording();
                      } else {
                        startRecording();
                        setUploadMethod("record");
                      }
                    }}
                    className={`p-4 rounded-xl border-2 transition-all ${
                      isRecording
                        ? "border-green-500 bg-green-50 animate-pulse"
                        : uploadMethod === "record"
                        ? "border-green-400 bg-green-50"
                        : "border-slate-200 bg-slate-50 hover:border-slate-300"
                    }`}
                  >
                    {isRecording ? (
                      <>
                        <Square className="w-6 h-6 mx-auto mb-2 text-green-500" />
                        <p className="text-sm font-bold text-green-600">
                          {Math.floor(recordingTime / 60)}:{(recordingTime % 60).toString().padStart(2, '0')}
                        </p>
                      </>
                    ) : (
                      <>
                        <Mic className={`w-6 h-6 mx-auto mb-2 ${
                          uploadMethod === "record" ? "text-green-500" : "text-slate-400"
                        }`} />
                        <p className={`text-sm font-bold ${
                          uploadMethod === "record" ? "text-green-600" : "text-slate-500"
                        }`}>Record</p>
                      </>
                    )}
                  </button>
                </div>

                {uploadMethod === "file" || uploadMethod === "record" ? (
                  <label htmlFor="audio-upload">
                    <div className="border-2 border-dashed border-slate-300 rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer hover:bg-slate-50 hover:border-blue-400 transition-colors group">
                      <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                        {uploadMethod === "record" && selectedFile ? (
                          <Mic className="w-6 h-6 text-green-500" />
                        ) : (
                          <FileAudio className="w-6 h-6 text-blue-500" />
                        )}
                      </div>
                      {selectedFile ? (
                        <>
                          <p className="font-bold text-slate-600 mb-1">
                            {uploadMethod === "record" ? "Recording saved!" : selectedFile.name}
                          </p>
                          <p className="text-xs text-slate-400 font-bold">
                            {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                            {uploadMethod === "record" && " (Ready to upload)"}
                          </p>
                        </>
                      ) : (
                        <>
                          <p className="font-bold text-slate-600 mb-1">Click to upload audio</p>
                          <p className="text-xs text-slate-400 font-bold uppercase">MP3, WAV up to 500MB</p>
                        </>
                      )}
                    </div>
                    <input
                      id="audio-upload"
                      type="file"
                      accept="audio/*,.mp3,.wav,.m4a,.flac,.ogg"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          setSelectedFile(file);
                          setUploadMethod("file");
                        }
                      }}
                    />
                  </label>
                ) : (
                  <div className="space-y-2">
                    <div className="relative">
                      <LinkIcon className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
                      <Input
                        type="url"
                        placeholder="https://www.youtube.com/watch?v=..."
                        value={youtubeUrl}
                        onChange={(e) => setYoutubeUrl(e.target.value)}
                        className="pl-10 h-12 rounded-xl border-2 border-slate-200 bg-slate-50 focus:border-red-400 focus:ring-0 font-medium text-slate-700"
                      />
                    </div>
                    <p className="text-xs text-slate-400 font-medium px-1">
                      Paste a YouTube video URL. The audio will be extracted and converted to MP3.
                    </p>
                  </div>
                )}
              </div>

              <div className="pt-4">
                <JuicyButton 
                  type="submit" 
                  className="w-full text-base py-4" 
                  variant="primary"
                  isLoading={isPending}
                >
                  {isPending ? "Uploading..." : "Upload Song"}
                </JuicyButton>
              </div>

            </form>
          </Form>
        </div>

        {form.formState.isSubmitSuccessful && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-6 bg-green-100 border-2 border-green-200 rounded-2xl p-4 flex items-center gap-4 text-green-700"
          >
            <CheckCircle2 className="w-8 h-8 flex-shrink-0" />
            <div>
              <p className="font-bold">Success!</p>
              <p className="text-sm">Sharing songs helps keep living languages alive!</p>
            </div>
          </motion.div>
        )}
      </main>
    </div>
  );
}
