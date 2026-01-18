import { Link, useLocation } from "wouter";
import { Music, Upload, User, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";

export function Navigation() {
  const [location] = useLocation();

  const NavItem = ({ href, icon: Icon, label }: { href: string; icon: any; label: string }) => {
    const isActive = location === href || (href === "/" && location === "/library");
    
    return (
      <Link href={href} className={cn(
        "flex flex-col md:flex-row items-center justify-center p-3 md:px-6 md:py-3 rounded-xl transition-all duration-200",
        "hover:bg-slate-100",
        isActive 
          ? "bg-blue-100 text-blue-500 border-2 border-blue-200" 
          : "text-slate-400 font-bold hover:text-slate-500"
      )}>
        <Icon className={cn("w-6 h-6 md:mr-3", isActive && "fill-current")} strokeWidth={2.5} />
        <span className="text-xs md:text-sm uppercase tracking-wide mt-1 md:mt-0">{label}</span>
      </Link>
    );
  };

  // Determine if we're in Singing or Learning section
  const isSingingSection = location === "/" || location === "/library" || location === "/upload";
  const isLearningSection = location === "/lessons";

  return (
    <>
      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t-2 border-slate-100 p-2 z-50 flex justify-around shadow-[0_-5px_20px_rgba(0,0,0,0.03)]">
        <NavItem href="/" icon={Music} label="Library" />
        <NavItem href="/upload" icon={Upload} label="Upload" />
        <NavItem href="/lessons" icon={BookOpen} label="Learning" />
        <NavItem href="/auth" icon={User} label="Login" />
      </nav>

      {/* Desktop Top Header Nav */}
      <nav className="hidden md:flex fixed top-0 left-0 right-0 bg-white border-b-2 border-slate-100 px-8 py-3 z-50 justify-between items-center">
        <div className="text-2xl font-black text-[#B878E8] tracking-tight flex items-center gap-2">
          <Music className="w-8 h-8" strokeWidth={3} />
          <span>Duosingo</span>
        </div>
        <div className="flex gap-4">
          <NavItem href="/" icon={Music} label="Library" />
          <NavItem href="/upload" icon={Upload} label="Upload" />
          <NavItem href="/lessons" icon={BookOpen} label="Learning" />
          <NavItem href="/auth" icon={User} label="Login" />
        </div>
      </nav>
      
      {/* Spacers to prevent content occlusion */}
      <div className="h-0 md:h-20" /> {/* Top spacer for desktop */}
    </>
  );
}
