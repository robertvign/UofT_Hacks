import type { Express } from "express";
import type { Server } from "http";
import { storage } from "./storage";
import { api } from "@shared/routes";
import { z } from "zod";

export async function registerRoutes(
  httpServer: Server,
  app: Express
): Promise<Server> {
  // Define routes using app.get(), app.post(), etc.
  
  app.get(api.songs.list.path, async (req, res) => {
    const songs = await storage.getSongs();
    res.json(songs);
  });

  app.get(api.songs.create.path, async (req, res) => {
    // This is a POST route in spec, but handled here for completeness if needed
    res.status(405).send("Method Not Allowed"); 
  });

  app.post(api.songs.create.path, async (req, res) => {
    try {
      const input = api.songs.create.input.parse(req.body);
      const song = await storage.createSong(input);
      res.status(201).json(song);
    } catch (err) {
      if (err instanceof z.ZodError) {
        return res.status(400).json({
          message: err.errors[0].message,
          field: err.errors[0].path.join('.'),
        });
      }
      throw err;
    }
  });

  app.put(api.songs.update.path, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const input = api.songs.update.input.parse(req.body);
      const song = await storage.updateSong(id, input);
      res.json(song);
    } catch (err) {
      if (err instanceof z.ZodError) {
         return res.status(400).json({
          message: err.errors[0].message,
          field: err.errors[0].path.join('.'),
        });
      }
      return res.status(404).json({ message: "Song not found" });
    }
  });

  app.delete(api.songs.delete.path, async (req, res) => {
    const id = parseInt(req.params.id);
    await storage.deleteSong(id);
    res.status(204).send();
  });

  return httpServer;
}
