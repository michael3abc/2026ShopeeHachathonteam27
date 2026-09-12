import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      className={cn(
        "h-11 w-full rounded-xl border border-stone-300 bg-white px-3.5 text-sm text-stone-950 outline-none placeholder:text-stone-400 focus:border-orange-500 focus:ring-3 focus:ring-orange-100 disabled:cursor-not-allowed disabled:bg-stone-100",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
