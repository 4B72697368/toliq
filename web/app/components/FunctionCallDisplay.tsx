"use client"

import { useState } from "react"

type FunctionCallDisplayProps = {
  callResponses: string[]
}

export default function FunctionCallDisplay({
  callResponses,
}: FunctionCallDisplayProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)

  if (!callResponses || callResponses.length === 0) {
    return null
  }

  const toggleExpand = (index: number) => {
    if (expandedIndex === index) {
      setExpandedIndex(null)
    } else {
      setExpandedIndex(index)
    }
  }

  return (
    <div className="w-full space-y-2 mt-2 text-sm">
      {callResponses.map((response, index) => {
        // Try to parse function calls from the response
        let functionCall = null
        let functionResult = null
        
        if (response.includes('<call:')) {
          try {
            // Extract function call JSON
            const callMatch = response.match(/<call:(.*?)>/)
            if (callMatch && callMatch[1]) {
              functionCall = JSON.parse(callMatch[1])
            }
          } catch (error) {
            console.error("Failed to parse function call:", error)
          }
        } else if (response.includes('Result of')) {
          try {
            // Extract platform, function name, and result
            const resultMatch = response.match(/Result of ([^:]+)\.([^:]+): (.*)/)
            if (resultMatch) {
              const [_, platform, func, resultStr] = resultMatch
              
              let parsedResult = resultStr
              try {
                // Try to parse the result as JSON
                parsedResult = JSON.parse(resultStr)
              } catch {
                // If it's not valid JSON, keep the string
              }
              
              functionResult = {
                platform,
                function: func,
                result: parsedResult
              }
            }
          } catch (error) {
            console.error("Failed to parse function result:", error)
          }
        }

        const isExpanded = expandedIndex === index
        const shouldShowToggle = response.length > 150

        return (
          <div
            key={index}
            className="p-2 rounded bg-gray-700 border border-gray-600 overflow-hidden"
          >
            {functionCall ? (
              <div className="text-blue-300">
                <span className="font-bold">Function Call: </span>
                <span className="font-mono">
                  {functionCall.platform}.{functionCall.function}
                </span>
                {functionCall.parameters && functionCall.parameters.length > 0 && (
                  <div className="pl-4 mt-1">
                    <span className="text-gray-400">Parameters:</span>
                    <pre className="ml-2 text-xs overflow-x-auto">
                      {JSON.stringify(functionCall.parameters, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ) : functionResult ? (
              <div className="text-green-300">
                <span className="font-bold">Result: </span>
                <span className="font-mono">
                  {functionResult.platform}.{functionResult.function}
                </span>
                <pre className="mt-1 text-xs overflow-x-auto pl-4 text-gray-300">
                  {JSON.stringify(functionResult.result, null, 2)}
                </pre>
              </div>
            ) : (
              <div>
                <pre className={`whitespace-pre-wrap font-mono text-xs ${shouldShowToggle && !isExpanded ? "line-clamp-3" : ""}`}>
                  {response}
                </pre>
                {shouldShowToggle && (
                  <button
                    className="text-blue-400 hover:text-blue-300 text-xs mt-1"
                    onClick={() => toggleExpand(index)}
                  >
                    {isExpanded ? "Show less" : "Show more"}
                  </button>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
} 