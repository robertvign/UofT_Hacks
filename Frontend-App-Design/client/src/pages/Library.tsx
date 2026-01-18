import { useSongs } from "@/hooks/use-songs";
import { SongCard } from "@/components/SongCard";
import { Navigation } from "@/components/Navigation";
import { Loader2, Music, Filter, X } from "lucide-react";
import { motion } from "framer-motion";
import { useState, useMemo } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export default function Library() {
  const { data: songs, isLoading } = useSongs();
  const [nameFilter, setNameFilter] = useState("");
  const [languageFilter, setLanguageFilter] = useState("");
  const [genreFilter, setGenreFilter] = useState("");
  
  // Get unique languages and genres for filter dropdowns
  const uniqueLanguages = useMemo(() => {
    if (!songs) return [];
    const langs = new Set(songs.map(s => s.language).filter(Boolean));
    return Array.from(langs).sort();
  }, [songs]);
  
  const uniqueGenres = useMemo(() => {
    if (!songs) return [];
    const genres = new Set(songs.map(s => (s as any).genre).filter(Boolean));
    return Array.from(genres).sort();
  }, [songs]);
  
  // Filter songs
  const filteredSongs = useMemo(() => {
    if (!songs) return [];
    return songs.filter(song => {
      const matchesName = !nameFilter || 
        song.title.toLowerCase().includes(nameFilter.toLowerCase()) ||
        ((song as any).artist?.toLowerCase().includes(nameFilter.toLowerCase()));
      const matchesLanguage = !languageFilter || song.language === languageFilter;
      const matchesGenre = !genreFilter || (song as any).genre === genreFilter;
      return matchesName && matchesLanguage && matchesGenre;
    });
  }, [songs, nameFilter, languageFilter, genreFilter]);
  
  const hasActiveFilters = nameFilter || languageFilter || genreFilter;
  
  const clearFilters = () => {
    setNameFilter("");
    setLanguageFilter("");
    setGenreFilter("");
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center">
        <Loader2 className="w-12 h-12 text-green-500 animate-spin mb-4" />
        <h2 className="text-xl font-bold text-slate-400">Loading your library...</h2>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white pb-24 md:pb-10">
      <Navigation />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header Section */}
        <div className="mb-8 md:mb-12 text-center md:text-left">
          <motion.h1 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-3xl md:text-4xl font-black text-slate-700 mb-2"
          >
            Language Library
          </motion.h1>
          <p className="text-slate-400 font-medium text-lg">
            Discover songs to keep languages alive.
          </p>
        </div>

        {/* Filter Section */}
        <div className="mb-8 bg-white rounded-2xl border-2 border-slate-100 p-4 md:p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <Filter className="w-5 h-5 text-slate-400" />
            <h2 className="font-bold text-slate-700 text-lg">Filters</h2>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="ml-auto flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X className="w-4 h-4" />
                Clear all
              </button>
            )}
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Name Filter */}
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                Name / Artist
              </label>
              <Input
                type="text"
                placeholder="Search by song or artist..."
                value={nameFilter}
                onChange={(e) => setNameFilter(e.target.value)}
                className="rounded-xl border-2 border-slate-200 bg-slate-50 h-10 focus:border-blue-400 focus:ring-0"
              />
            </div>
            
            {/* Language Filter */}
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                Language
              </label>
              <select
                value={languageFilter}
                onChange={(e) => setLanguageFilter(e.target.value)}
                className="w-full rounded-xl border-2 border-slate-200 bg-slate-50 h-10 px-3 focus:border-blue-400 focus:ring-0 font-medium text-slate-700"
              >
                <option value="">All Languages</option>
                {uniqueLanguages.map(lang => (
                  <option key={lang} value={lang}>{lang}</option>
                ))}
              </select>
            </div>
            
            {/* Genre Filter */}
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                Genre
              </label>
              <select
                value={genreFilter}
                onChange={(e) => setGenreFilter(e.target.value)}
                className="w-full rounded-xl border-2 border-slate-200 bg-slate-50 h-10 px-3 focus:border-blue-400 focus:ring-0 font-medium text-slate-700"
              >
                <option value="">All Genres</option>
                {uniqueGenres.map(genre => (
                  <option key={genre} value={genre}>{genre}</option>
                ))}
              </select>
            </div>
          </div>
          
          {hasActiveFilters && (
            <div className="mt-4 text-sm text-slate-500">
              Showing {filteredSongs.length} of {songs?.length || 0} songs
            </div>
          )}
        </div>

        {/* Grid */}
        {filteredSongs && filteredSongs.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 md:gap-8">
            {filteredSongs.map((song) => (
              <SongCard key={song.id} song={song} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="bg-slate-100 p-8 rounded-full mb-6">
              <Music className="w-16 h-16 text-slate-300" />
            </div>
            <h3 className="text-xl font-bold text-slate-600 mb-2">
              {hasActiveFilters ? "No songs match your filters" : "No songs yet"}
            </h3>
            <p className="text-slate-400 max-w-md mx-auto">
              {hasActiveFilters 
                ? "Try adjusting your filters to see more results."
                : "Be the first to contribute a song to the library!"}
            </p>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="mt-4 px-4 py-2 bg-green-500 text-white rounded-xl font-bold hover:bg-green-600 transition-colors"
              >
                Clear Filters
              </button>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
