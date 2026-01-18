# Quick Start Guide

## Running the Frontend Application

### Step 1: Install Dependencies
```bash
cd Frontend-App-Design
npm install
```

### Step 2: Run the Development Server
```bash
npm run dev
```

The application will start on **http://localhost:1234** (or the port specified in the `PORT` environment variable).

### What This Does
- Starts the Express backend server
- Starts the Vite development server for the React frontend
- Both frontend and backend are served from the same port (1234)
- Hot module replacement (HMR) is enabled for fast development

### Other Available Commands

- **Build for production**: `npm run build`
- **Start production server**: `npm start` (after building)
- **Type check**: `npm run check`
- **Database migrations**: `npm run db:push`

### Environment Variables

The app uses a mock database connection by default. If you need a real PostgreSQL database, set:
```bash
export DATABASE_URL="postgres://user:password@localhost:5432/dbname"
```

### Troubleshooting

If you encounter port conflicts, you can specify a different port:
```bash
PORT=3000 npm run dev
```

