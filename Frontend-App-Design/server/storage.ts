import { type Song, type InsertSong } from "@shared/schema";

export interface IStorage {
  getSongs(): Promise<Song[]>;
  getSong(id: number): Promise<Song | undefined>;
  createSong(song: InsertSong): Promise<Song>;
  updateSong(id: number, song: Partial<InsertSong>): Promise<Song>;
  deleteSong(id: number): Promise<void>;
}

export class MemStorage implements IStorage {
  private songs: Map<number, Song>;
  private currentId: number;

  constructor() {
    this.songs = new Map();
    this.currentId = 1;
  }

  async getSongs(): Promise<Song[]> {
    return Array.from(this.songs.values());
  }

  async getSong(id: number): Promise<Song | undefined> {
    return this.songs.get(id);
  }

  async createSong(insertSong: InsertSong): Promise<Song> {
    const id = this.currentId++;
    const song: Song = { ...insertSong, id, progress: insertSong.progress ?? 0, isFavorite: insertSong.isFavorite ?? false, region: insertSong.region ?? null, coverUrl: insertSong.coverUrl ?? null };
    this.songs.set(id, song);
    return song;
  }

  async updateSong(id: number, updates: Partial<InsertSong>): Promise<Song> {
    const existing = await this.getSong(id);
    if (!existing) {
      throw new Error("Song not found");
    }
    const updated = { ...existing, ...updates };
    this.songs.set(id, updated);
    return updated;
  }

  async deleteSong(id: number): Promise<void> {
    this.songs.delete(id);
  }
}

export const storage = new MemStorage();
