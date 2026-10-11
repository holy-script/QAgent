import { AuthGate } from "@/components/auth-gate";
import View from "./view";

// Data is fetched in the browser after sign-in, so these pages cannot be pre-rendered for instant navigation.
export const instant = false;

export default function Page() {
  return <AuthGate><View /></AuthGate>;
}
