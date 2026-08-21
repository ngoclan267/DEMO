"use client";

import { useParams } from "next/navigation";
import { SocialStreamPage } from "@/components/social/SocialStreamPage";
import { TIKTOK_PLATFORM_CONFIG } from "@/lib/socialPlatforms";

export default function TikTokStreamPage() {
  const { id } = useParams<{ id: string }>();
  return <SocialStreamPage topicId={id} config={TIKTOK_PLATFORM_CONFIG} />;
}
