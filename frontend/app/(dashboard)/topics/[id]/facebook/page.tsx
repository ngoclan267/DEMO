"use client";

import { useParams } from "next/navigation";
import { SocialStreamPage } from "@/components/social/SocialStreamPage";
import { FACEBOOK_PLATFORM_CONFIG } from "@/lib/socialPlatforms";

export default function FacebookStreamPage() {
  const { id } = useParams<{ id: string }>();
  return <SocialStreamPage topicId={id} config={FACEBOOK_PLATFORM_CONFIG} />;
}
