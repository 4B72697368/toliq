"use client"

import type React from "react"
import { useState, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import { ArrowRight, Settings } from "lucide-react"
import FunctionCallDisplay from "./components/FunctionCallDisplay"

type Message = {
  role: "user" | "assistant"
  content: string
  functionCalls?: string[] // To store function call responses
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState("")
  const [isHovering, setIsHovering] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
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

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  const sendRequest = async () => {
    if (isSubmitting || !inputValue.trim()) return

    setIsSubmitting(true)
    
    // Add user message to chat
    const userMessage = { role: "user" as const, content: inputValue }
    setMessages((prevMessages) => [...prevMessages, userMessage])
    setInputValue("")

    const user = JSON.parse(localStorage.getItem("user") || "{}")

    try {
      const res = await fetch("/api/proxy", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          input: userMessage.content,
          user: user,
        }),
      })

      if (!res.ok) {
        const errorText = await res.text()
        console.error(`Server responded with ${res.status}: ${errorText}`)
        setMessages((prevMessages) => [
          ...prevMessages,
          { role: "assistant", content: `Error: ${res.status} - ${errorText.substring(0, 100)}` },
        ])
        throw new Error(`Server responded with ${res.status}: ${errorText.substring(0, 100)}`)
      }

      const data = await res.json()
      console.log("✅ Server response:", data)
      
      // Add assistant response to chat with function calls if available
      setMessages((prevMessages) => [
        ...prevMessages,
        { 
          role: "assistant", 
          content: data.output,
          functionCalls: data.call_responses || [] 
        },
      ])
    } catch (err) {
      console.error("❌ Error sending request:", err)
      if (!messages.some(m => m.role === "assistant" && m.content.startsWith("Error:"))) {
        setMessages((prevMessages) => [
          ...prevMessages,
          { 
            role: "assistant", 
            content: `Error: ${err instanceof Error ? err.message : "Failed to connect to server"}` 
          },
        ])
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      sendRequest()
    }
  }

  return (
    <main className="flex min-h-screen flex-col bg-gray-900 text-gray-100 p-4 relative">
      {/* Settings button */}
      <button
        onClick={() => router.push("/settings")}
        className="absolute top-4 right-4 text-gray-400 hover:text-white transition"
      >
        <Settings className="h-6 w-6" />
      </button>

      <div className="w-full max-w-4xl mx-auto flex flex-col h-screen pt-12 pb-4">
        <h1 className="text-4xl font-bold mb-6 text-center transition-all duration-300">
          {isHovering ? "pilot" : "toliq"}
        </h1>

        {/* Chat messages */}
        <div className="flex-1 overflow-y-auto mb-4">
          <div className="space-y-6 mb-6">
            {messages.length === 0 ? (
              <div className="text-center text-gray-500 my-20">
                <p>Start a conversation by typing a message below</p>
              </div>
            ) : (
              messages.map((message, index) => (
                <div key={index} className="space-y-2">
                  <div
                    className={`flex ${
                      message.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-3xl p-4 rounded-lg ${
                        message.role === "user"
                          ? "bg-blue-600 text-white"
                          : "bg-gray-800 border border-gray-700"
                      }`}
                    >
                      <pre className="whitespace-pre-wrap font-sans">{message.content}</pre>
                    </div>
                  </div>
                  
                  {/* Display function calls if available */}
                  {message.role === "assistant" && message.functionCalls && message.functionCalls.length > 0 && (
                    <div className={`flex justify-start pl-6`}>
                      <div className="max-w-3xl w-full">
                        <FunctionCallDisplay callResponses={message.functionCalls} />
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input area */}
        <div className="relative mt-auto">
          <input
            type="text"
            placeholder="Type something and press Enter..."
            className="w-full h-16 px-6 py-4 text-lg bg-gray-800 border border-gray-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-gray-600 focus:border-gray-600"
            onKeyDown={handleKeyDown}
            onChange={(e) => setInputValue(e.target.value)}
            value={inputValue}
            autoFocus
            disabled={isSubmitting}
          />
          <button
            className={`absolute right-4 top-1/2 transform -translate-y-1/2 h-10 w-10 rounded-full ${
              isSubmitting ? "bg-gray-600" : "bg-gray-700 hover:bg-gray-600"
            } flex items-center justify-center transition-colors`}
            onClick={sendRequest}
            onMouseEnter={() => setIsHovering(true)}
            onMouseLeave={() => setIsHovering(false)}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <div className="h-5 w-5 border-t-2 border-blue-500 rounded-full animate-spin" />
            ) : (
              <ArrowRight className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>
    </main>
  )
}
