import React from "react";
import { Navigation } from "@/components/Navigation";
import { Loader2, BookOpen, Mic, CheckCircle2, Square, Globe } from "lucide-react";
import { motion } from "framer-motion";
import { JuicyButton } from "@/components/JuicyButton";
import { useLessons, useGenerateLessons, useSavePracticeRecording } from "@/hooks/use-lessons";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function Lessons() {
  const { data: lessons, isLoading, refetch } = useLessons();
  const { mutate: generateLessons, isPending: isGenerating } = useGenerateLessons();
  const { mutate: saveRecording } = useSavePracticeRecording();
  
  const [currentPracticeIndex, setCurrentPracticeIndex] = React.useState<number | null>(null);
  const [isRecording, setIsRecording] = React.useState(false);
  const [mediaRecorder, setMediaRecorder] = React.useState<MediaRecorder | null>(null);
  const [practiceRecordings, setPracticeRecordings] = React.useState<Record<number, string>>({});
  const [selectedLanguage, setSelectedLanguage] = React.useState("fr-fr");

  const handleGenerateLessons = () => {
    generateLessons(
      { language: selectedLanguage, num_conversations: 3 },
      {
        onSuccess: () => {
          refetch();
        },
      }
    );
  };

  const startRecording = async (index: number) => {
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
        
        // Save recording using the hook
        saveRecording(
          { audioBlob: blob, conversationIndex: index },
          {
            onSuccess: (result) => {
              setPracticeRecordings(prev => ({
                ...prev,
                [index]: result.recording_path || 'saved'
              }));
            },
          }
        );
        
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
      };
      
      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
      setCurrentPracticeIndex(index);
    } catch (error) {
      console.error("Error starting recording:", error);
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
      setMediaRecorder(null);
      setCurrentPracticeIndex(null);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center">
        <Loader2 className="w-12 h-12 text-green-500 animate-spin mb-4" />
        <h2 className="text-xl font-bold text-slate-400">Loading lessons...</h2>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white pb-24 md:pb-10">
      <Navigation />
      
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header Section */}
        <div className="mb-8 md:mb-12 text-center md:text-left">
          <div className="flex items-center justify-between mb-4">
            <div>
              <motion.h1 
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-3xl md:text-4xl font-black text-slate-700 mb-2"
              >
                Pronunciation Lessons
              </motion.h1>
              <p className="text-slate-400 font-medium text-lg">
                Practice words you struggle with through conversational exercises.
              </p>
            </div>
            {lessons && (
              <JuicyButton
                onClick={() => refetch()}
                variant="secondary"
                className="hidden md:flex"
              >
                Refresh
              </JuicyButton>
            )}
          </div>
        </div>

        {!lessons ? (
          <div className="bg-white rounded-3xl border-2 border-slate-100 p-8 md:p-12 shadow-sm text-center">
            <div className="bg-slate-100 p-8 rounded-full mb-6 inline-block">
              <BookOpen className="w-16 h-16 text-slate-300" />
            </div>
            <h3 className="text-xl font-bold text-slate-600 mb-2">
              No lessons yet
            </h3>
            <p className="text-slate-400 max-w-md mx-auto mb-6">
              Generate personalized lessons based on your pronunciation profile. 
              Practice words you've struggled with in a conversational context.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 items-center justify-center">
              <div className="flex items-center gap-2">
                <Globe className="w-5 h-5 text-slate-400" />
                <Select value={selectedLanguage} onValueChange={setSelectedLanguage}>
                  <SelectTrigger className="w-40 border-2 border-slate-200 rounded-xl">
                    <SelectValue placeholder="Language" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fr-fr">French</SelectItem>
                    <SelectItem value="en-us">English</SelectItem>
                    <SelectItem value="es-es">Spanish</SelectItem>
                    <SelectItem value="de-de">German</SelectItem>
                    <SelectItem value="it-it">Italian</SelectItem>
                    <SelectItem value="pt-pt">Portuguese</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <JuicyButton
                onClick={handleGenerateLessons}
                isLoading={isGenerating}
                variant="primary"
                className="px-8 py-3"
              >
                {isGenerating ? "Generating..." : "Generate Lessons"}
              </JuicyButton>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {lessons.conversations && lessons.conversations.length > 0 ? (
              lessons.conversations.map((conv, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className="bg-white rounded-3xl border-2 border-slate-100 p-6 md:p-8 shadow-sm"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm font-bold text-blue-500 bg-blue-50 px-3 py-1 rounded-full">
                          Word {index + 1}
                        </span>
                        <span className="text-xs text-slate-400">
                          Error Rate: {(conv.error_rate * 100).toFixed(1)}%
                        </span>
                      </div>
                      <h3 className="text-lg font-bold text-slate-700 mb-1">
                        Target Word: <span className="text-green-500">{conv.target_word}</span>
                      </h3>
                    </div>
                    {practiceRecordings[index] && (
                      <CheckCircle2 className="w-6 h-6 text-green-500 flex-shrink-0" />
                    )}
                  </div>

                  <div className="space-y-4">
                    <div className="bg-blue-50 rounded-2xl p-4 border-2 border-blue-100">
                      <p className="text-xs font-bold text-blue-400 uppercase tracking-wide mb-2">
                        Question
                      </p>
                      <p className="text-slate-700 font-medium text-lg">
                        {conv.question}
                      </p>
                    </div>

                    <div className="bg-green-50 rounded-2xl p-4 border-2 border-green-100">
                      <p className="text-xs font-bold text-green-400 uppercase tracking-wide mb-2">
                        Your Response (Practice saying this)
                      </p>
                      <p className="text-slate-700 font-medium text-lg">
                        {conv.response}
                      </p>
                    </div>

                    <div className="flex gap-3 pt-2">
                      {currentPracticeIndex === index && isRecording ? (
                        <JuicyButton
                          onClick={stopRecording}
                          variant="destructive"
                          className="flex-1"
                        >
                          <Square className="w-5 h-5 mr-2" />
                          Stop Recording
                        </JuicyButton>
                      ) : (
                        <JuicyButton
                          onClick={() => startRecording(index)}
                          variant="primary"
                          className="flex-1"
                          disabled={currentPracticeIndex !== null && currentPracticeIndex !== index}
                        >
                          <Mic className="w-5 h-5 mr-2" />
                          {practiceRecordings[index] ? "Record Again" : "Practice & Record"}
                        </JuicyButton>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))
            ) : (
              <div className="bg-white rounded-3xl border-2 border-slate-100 p-8 text-center">
                <p className="text-slate-400 mb-4">No conversations in this lesson.</p>
                <JuicyButton
                  onClick={handleGenerateLessons}
                  isLoading={isGenerating}
                  variant="primary"
                >
                  Generate New Lessons
                </JuicyButton>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

