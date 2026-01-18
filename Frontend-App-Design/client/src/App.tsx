import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/not-found";
import Library from "@/pages/Library";
import Upload from "@/pages/Upload";
import AuthPage from "@/pages/AuthPage";
import Lessons from "@/pages/Lessons";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Library} />
      <Route path="/library" component={Library} />
      <Route path="/upload" component={Upload} />
      <Route path="/lessons" component={Lessons} />
      <Route path="/auth" component={AuthPage} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Router />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
