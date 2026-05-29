import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        blue: "border-transparent bg-blue-100 text-blue-800",
        green: "border-transparent bg-green-100 text-green-800",
        gray: "border-transparent bg-gray-100 text-gray-600",
        success: "border-transparent bg-green-100 text-green-800",
        failed: "border-transparent bg-red-100 text-red-800",
        skipped: "border-transparent bg-yellow-100 text-yellow-800",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, colorClass, ...props }: BadgeProps & { colorClass?: string }) {
  return <span className={cn(badgeVariants({ variant }), colorClass, className)} {...props} />;
}

export { Badge, badgeVariants };
