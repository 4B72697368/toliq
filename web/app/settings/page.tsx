"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

export default function Settings() {
  const router = useRouter()
  const [user, setUser] = useState({
    calendarEndpoint: "",
    gsheetsEndpoint: "",
  })

  useEffect(() => {
    const storedUser = localStorage.getItem("user")
    if (storedUser) {
      setUser(JSON.parse(storedUser))
    }
  }, [])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setUser((prev) => ({ ...prev, [name]: value }))
  }

  const handleSave = () => {
    localStorage.setItem("user", JSON.stringify(user))
    router.push("/")
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-900 text-gray-100 p-4">
      <div className="w-full max-w-md space-y-6">
        <h1 className="text-3xl font-bold text-center">Settings</h1>

        <div className="space-y-4">
          <div>
            <label className="block mb-1 text-sm">Calendar Endpoint</label>
            <input
              type="text"
              name="calendarEndpoint"
              value={user.calendarEndpoint}
              onChange={handleChange}
              className="w-full p-2 rounded bg-gray-800 border border-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-gray-600"
            />
          </div>

          <div>
            <label className="block mb-1 text-sm">Google Sheets Endpoint</label>
            <input
              type="text"
              name="gsheetsEndpoint"
              value={user.gsheetsEndpoint}
              onChange={handleChange}
              className="w-full p-2 rounded bg-gray-800 border border-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-gray-600"
            />
          </div>

          <button
            onClick={handleSave}
            className="w-full py-2 px-4 rounded bg-gray-700 hover:bg-gray-600 text-white transition-colors"
          >
            Save
          </button>
        </div>
      </div>
    </main>
  )
}