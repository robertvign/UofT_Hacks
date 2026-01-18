import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, forwardRef } from "react";

interface JuicyButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "accent" | "ghost";
  isLoading?: boolean;
}

export const JuicyButton = forwardRef<HTMLButtonElement, JuicyButtonProps>(
  ({ className, children, variant = "primary", isLoading, disabled, ...props }, ref) => {
    
    const variants = {
      primary: "bg-[hsl(var(--primary))] text-white border-[hsl(var(--primary-depth))] hover:bg-[hsl(var(--primary))]/90",
      secondary: "bg-[hsl(var(--secondary))] text-white border-[hsl(var(--secondary-depth))] hover:bg-[hsl(var(--secondary))]/90",
      accent: "bg-[hsl(var(--accent))] text-slate-800 border-yellow-600 hover:bg-[hsl(var(--accent))]/90",
      ghost: "bg-transparent text-slate-500 border-transparent shadow-none hover:bg-slate-100 border-b-0 active:translate-y-0",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          // Base
          "relative inline-flex items-center justify-center rounded-2xl px-8 py-3 font-extrabold uppercase tracking-wider text-sm transition-all outline-none focus:ring-4 focus:ring-slate-200",
          // 3D Effect
          variant !== "ghost" && "border-b-[4px] active:border-b-0 active:translate-y-[4px]",
          // Disabled state
          (disabled || isLoading) && "opacity-60 cursor-not-allowed active:border-b-[4px] active:translate-y-0",
          variants[variant],
          className
        )}
        {...props}
      >
        {isLoading ? (
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            <span>Loading...</span>
          </div>
        ) : children}
      </button>
    );
  }
);
