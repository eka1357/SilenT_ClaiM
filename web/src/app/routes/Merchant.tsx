import { Link } from "react-router-dom";
import { PhoneFrame } from "@/components/PhoneFrame";
import { PhoneStatusPill } from "@/components/PhoneStatusPill";
import { ShareDisclosure } from "@/components/ShareDisclosure";

export function Merchant() {
  return (
    <div className="min-h-screen bg-[var(--ink)] p-6 text-[var(--text-dark-1)]">
      <div className="mx-auto mb-4 flex max-w-[390px] items-center justify-between">
        <Link
          to="/console"
          className="text-[13px] font-medium text-[var(--marigold)] underline underline-offset-2"
        >
          Back to /console
        </Link>
      </div>
      <PhoneFrame>
        <div className="flex flex-1 flex-col justify-between gap-4">
          <PhoneStatusPill state="Covered" shopName="Selvi Flowers" />
          <ShareDisclosure />
        </div>
      </PhoneFrame>
    </div>
  );
}

