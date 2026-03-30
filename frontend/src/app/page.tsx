"use client";

import { useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import UploadPanel from "@/components/UploadPanel";

type Tab = "analytics" | "documents";

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("analytics");

  return (
    <main className="min-h-screen p-4">
      <div className="flex gap-4 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab("analytics")}
          className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "analytics"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Analytics
        </button>
        <button
          onClick={() => setActiveTab("documents")}
          className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "documents"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Documents
        </button>
      </div>
      {activeTab === "analytics" ? <ChatPanel /> : <UploadPanel />}
    </main>
  );
}
