# Duosingo

## Overview

Duosingo is a web application designed to help people reclaim and rekindle ancestral languages affected by colonization, using music as a bridge for learning, memory, and cultural continuity. The app features a Duolingo-inspired visual style with bright but soft colors, rounded UI elements, and friendly typography.

The application is built as a full-stack TypeScript project with a React frontend and Express backend, though it currently operates primarily with mock data for client-side demonstration purposes.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: React 18 with TypeScript
- **Routing**: Wouter for lightweight client-side routing
- **State Management**: TanStack React Query for server state and caching
- **Styling**: Tailwind CSS with custom Duolingo-inspired theme (bright greens, blues, yellows)
- **UI Components**: shadcn/ui component library built on Radix UI primitives
- **Animations**: Framer Motion for smooth, "juicy" UI interactions
- **Forms**: React Hook Form with Zod validation

### Backend Architecture
- **Framework**: Express 5 on Node.js
- **Database ORM**: Drizzle ORM with PostgreSQL dialect
- **Schema Validation**: Zod with drizzle-zod integration
- **Storage**: In-memory storage class (MemStorage) for development, designed to be swapped with database storage

### Build System
- **Frontend Build**: Vite for development server and production builds
- **Backend Build**: esbuild for bundling server code
- **TypeScript**: Strict mode enabled with path aliases (@/, @shared/)

### Project Structure
```
client/           # React frontend application
  src/
    components/   # Reusable UI components
    pages/        # Route pages (Library, Upload, AuthPage)
    hooks/        # Custom React hooks
    lib/          # Utilities and query client
server/           # Express backend
shared/           # Shared types, schemas, and API route definitions
```

### API Design
- RESTful API structure defined in `shared/routes.ts`
- Type-safe route definitions with Zod schemas for input validation and response types
- Currently uses mock data in frontend hooks to simulate API responses

### Data Model
The primary entity is a `Song` with fields:
- id, title, language, region (optional), coverUrl (optional)
- progress (0-100 for learning progress)
- isFavorite (boolean)

## External Dependencies

### Database
- **PostgreSQL**: Configured via DATABASE_URL environment variable
- **Drizzle Kit**: For database migrations (`npm run db:push`)

### UI Libraries
- **Radix UI**: Full suite of accessible primitives (dialog, dropdown, tabs, etc.)
- **Lucide React**: Icon library
- **embla-carousel-react**: Carousel component
- **vaul**: Drawer component
- **cmdk**: Command palette component

### Development Tools
- **Vite Plugins**: Runtime error overlay, Replit-specific dev tools (cartographer, dev banner)
- **PostCSS/Autoprefixer**: CSS processing

### Fonts
- **Nunito**: Primary font family (loaded via Google Fonts)
- **DM Sans, Fira Code, Geist Mono**: Additional font options