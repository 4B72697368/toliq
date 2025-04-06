"use client"

import type React from "react"
import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { ArrowRight, Settings } from "lucide-react"

export default function Home() {
  const [showInput, setShowInput] = useState(true)
  const [isHovering, setIsHovering] = useState(false)
  const [inputValue, setInputValue] = useState("")
  const router = useRouter()

  useEffect(() => {
    const existingUser = localStorage.getItem("user")
    if (!existingUser) {
      localStorage.setItem(
        "user",
        JSON.stringify({
          calendarEndpoint: "",
          gsheetsEndpoint: "",
        })
      )
    }
  }, [])

  const [isSubmitting, setIsSubmitting] = useState(false);

  const sendRequest = async () => {
    if (isSubmitting) return;

    setIsSubmitting(true);

    const user = JSON.parse(localStorage.getItem("user") || "{}");

    try {
      const res = await fetch("http://localhost:5000/message", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          input: inputValue,
          user: user,
        }),
      });

      if (!res.ok) {
        throw new Error(`Server responded with ${res.status}`);
      }

      const data = await res.json();
      console.log("✅ Server response:", data);

      setShowInput(false);
    } catch (err) {
      console.error("❌ Error sending request:", err);
    } finally {
      setIsSubmitting(false);
    }

    console.log("📦 User object:", user);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      sendRequest()
    }
  }

  const handleSubmit = () => {
    sendRequest()
  }

  const placeholderBlocks = ["jas;ldfjasldfkjad", "asldfjasldkfjasldf", "aldfkjaslfjad"]

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-900 text-gray-100 p-4 relative">
      {/* Settings button */}
      <button
        onClick={() => router.push("/settings")}
        className="absolute top-4 right-4 text-gray-400 hover:text-white transition"
      >
        <Settings className="h-6 w-6" />
      </button>

      {showInput ? (
        <div className="w-full max-w-3xl">
          <h1 className="text-4xl font-bold mb-6 text-center transition-all duration-300">
            {isHovering ? "pilot" : "toliq"}
          </h1>

          <div className="relative">
            <input
              type="text"
              placeholder="Type something and press Enter..."
              className="w-full h-16 px-6 py-8 text-lg bg-gray-800 border border-gray-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-gray-600 focus:border-gray-600"
              onKeyDown={handleKeyDown}
              onChange={(e) => setInputValue(e.target.value)}
              value={inputValue}
              autoFocus
            />
            <button
              className="absolute right-4 top-1/2 transform -translate-y-1/2 h-10 w-10 rounded-full bg-gray-700 hover:bg-gray-600 flex items-center justify-center transition-colors"
              onClick={handleSubmit}
              onMouseEnter={() => setIsHovering(true)}
              onMouseLeave={() => setIsHovering(false)}
            >
              <ArrowRight className="h-5 w-5" />
            </button>
          </div>
        </div>
      ) : (
        <div className="w-full max-w-lg space-y-6">
          {placeholderBlocks.map((block, index) => (
            <div
              key={index}
              className="bg-gray-800 p-6 rounded-lg border border-gray-700 hover:border-gray-500 transition-colors w-full"
            >
              <p>{block}</p>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}
