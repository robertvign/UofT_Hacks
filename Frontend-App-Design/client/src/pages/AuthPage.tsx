import { useState } from "react";
import { useLocation } from "wouter";
import { motion } from "framer-motion";
import { Music, ArrowRight, Lock, User as UserIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/hooks/use-auth";

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  const { login, isLoggingIn, loginError } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleAuth = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      toast({
        title: "Missing credentials",
        description: "Please enter both username and password",
        variant: "destructive",
      });
      return;
    }
    
    login(
      { username, password },
      {
        onSuccess: () => {
          toast({
            title: "Welcome back!",
            description: "You're now ready to reclaim ancestral songs.",
            className: "bg-green-500 text-white border-none shadow-xl",
          });
          setLocation("/");
        },
        onError: (error: any) => {
          toast({
            title: "Login failed",
            description: error.message || "Invalid username or password",
            variant: "destructive",
          });
        },
      }
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        <div className="flex flex-col items-center mb-8">
          <div className="bg-green-500 p-4 rounded-3xl shadow-lg mb-4 hover-elevate transition-transform">
            <Music className="w-10 h-10 text-white" strokeWidth={2.5} />
          </div>
          <h1 className="text-4xl font-black text-slate-800 tracking-tight">Duosingo</h1>
          <p className="text-slate-500 font-medium text-center mt-2 max-w-xs">
            {isLogin 
              ? "Reclaim your ancestral voice through the power of song." 
              : "Join our community and help keep living languages alive."}
          </p>
        </div>

        <Card className="border-2 border-slate-100 shadow-xl rounded-3xl overflow-hidden">
          <CardHeader className="bg-white pb-2">
            <CardTitle className="text-2xl font-bold text-slate-700">
              {isLogin ? "Welcome back" : "Create your account"}
            </CardTitle>
            <CardDescription className="text-slate-400 font-medium">
              {isLogin ? "Pick up where you left off" : "Start your language journey today"}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <form onSubmit={handleAuth} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <div className="relative">
                  <UserIcon className="absolute left-3 top-3 w-4 h-4 text-slate-400" />
                  <Input 
                    id="username" 
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Enter your username" 
                    className="pl-10 h-11 rounded-xl border-2 focus-visible:ring-green-500" 
                    required 
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-3 w-4 h-4 text-slate-400" />
                  <Input 
                    id="password" 
                    type="password" 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••" 
                    className="pl-10 h-11 rounded-xl border-2 focus-visible:ring-green-500" 
                    required 
                  />
                </div>
              </div>
              {loginError && (
                <div className="bg-red-50 border-2 border-red-200 rounded-xl p-3 text-sm text-red-700">
                  {String(loginError)}
                </div>
              )}
              <Button 
                type="submit" 
                disabled={isLoggingIn}
                className="w-full h-12 rounded-2xl bg-green-500 hover:bg-green-600 text-white font-bold text-lg shadow-lg shadow-green-200/50 mt-4 group disabled:opacity-50"
              >
                {isLoggingIn ? "Signing in..." : "Sign In"}
                {!isLoggingIn && <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />}
              </Button>
            </form>
          </CardContent>
          <CardFooter className="bg-slate-50 border-t-2 border-slate-100 flex flex-col gap-4 py-6">
          </CardFooter>
        </Card>

        <p className="text-center mt-8 text-slate-400 text-xs font-medium px-8 leading-relaxed">
          By continuing, you agree to Duosingo's 
          <span className="text-slate-500 font-bold"> Terms of Service </span> 
          and <span className="text-slate-500 font-bold"> Privacy Policy</span>.
        </p>
      </motion.div>
    </div>
  );
}

