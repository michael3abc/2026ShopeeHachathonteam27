import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      className={cn(
        "min-h-28 w-full resize-y rounded-xl border border-stone-300 bg-white px-3.5 py-3 text-sm leading-6 text-stone-950 outline-none placeholder:text-stone-400 focus:border-orange-500 focus:ring-3 focus:ring-orange-100 disabled:cursor-not-allowed disabled:bg-stone-100",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
