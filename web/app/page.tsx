"use client"

import type React from "react"
import { useState, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import { ArrowRight, Settings, Trash2 } from "lucide-react"
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

  // Load messages from localStorage on component mount
  useEffect(() => {
    const savedMessages = localStorage.getItem("chatMessages")
    if (savedMessages) {
      try {
        setMessages(JSON.parse(savedMessages))
      } catch (e) {
        console.error("Failed to parse saved messages:", e)
      }
    }

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

  // Save messages to localStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem("chatMessages", JSON.stringify(messages))
    }
  }, [messages])

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
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
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
          conversation_history: updatedMessages.slice(-10) // Send last 10 messages for context
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

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault(); // Prevent default to avoid adding a new line
      sendRequest();
    }
  }

  // Auto-resize textarea based on content
  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const textarea = e.target;
    setInputValue(textarea.value);
    
    // Reset height to auto to get the right scrollHeight
    textarea.style.height = 'auto';
    
    // Set to scrollHeight to expand properly
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 56), 200); // min 56px, max 200px
    textarea.style.height = `${newHeight}px`;
  }

  const clearConversation = () => {
    setMessages([]);
    localStorage.removeItem("chatMessages");
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
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-4xl font-bold text-center transition-all duration-300 flex-grow">
            {isHovering ? "pilot" : "toliq"}
          </h1>
          {messages.length > 0 && (
            <button
              onClick={clearConversation}
              className="text-gray-400 hover:text-white transition flex items-center gap-1"
              title="Clear conversation"
            >
              <Trash2 className="h-5 w-5" />
              <span className="text-sm">Clear</span>
            </button>
          )}
        </div>

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
          <textarea
            placeholder="Type something and press Enter... (Shift+Enter for new line)"
            className="w-full min-h-[56px] max-h-[200px] px-6 py-4 text-lg bg-gray-800 border border-gray-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-gray-600 focus:border-gray-600 resize-none overflow-auto"
            onKeyDown={handleKeyDown}
            onChange={handleTextareaChange}
            value={inputValue}
            autoFocus
            disabled={isSubmitting}
            rows={1}
          />
          <button
            className={`absolute right-4 bottom-[14px] h-10 w-10 rounded-full ${
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
