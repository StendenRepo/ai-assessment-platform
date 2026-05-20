'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const handleSubmit = (e) => {
    e.preventDefault();
    router.push('/dashboard');
  };
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="border-4 border-gray-400 bg-white p-8 mb-6 text-center">
          <div className="text-4xl font-bold mb-2">[LOGO]</div>
          <div className="text-2xl font-bold">AI Assessment System</div>
          <div className="text-sm text-gray-600 mt-2">
            Group Project Evaluation Platform
          </div>
        </div>

        <div className="border-4 border-gray-400 bg-white p-8">
          <h2 className="text-xl font-bold mb-6">Login</h2>

          <form onSubmit={handleSubmit}>
            <div className="mb-6">
              <label className="block font-bold mb-2">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border-2 border-gray-400 px-4 py-3"
                placeholder="name@university.edu"
              />
            </div>

            <div className="mb-6">
              <label className="block font-bold mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border-2 border-gray-400 px-4 py-3"
                placeholder="••••••••"
              />
            </div>

            <div className="mb-6">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="w-4 h-4 border-2 border-gray-400"
                />
                <span className="text-sm">Remember me</span>
              </label>
            </div>

            <button
              type="submit"
              className="w-full border-2 border-gray-400 bg-gray-900 text-white px-6 py-4 font-bold hover:bg-gray-700 mb-4"
            >
              [LOGIN →]
            </button>

            <div className="text-center text-sm">
              <a href="#" className="text-gray-600 hover:underline">
                Forgot password?
              </a>
            </div>
          </form>
        </div>

        <div className="border-2 border-gray-400 bg-white p-4 mt-6">
          <div className="text-xs">
            <div className="font-bold mb-2">[i] Privacy & Security</div>
            <p className="text-gray-600">
              This system processes all data on-premises and complies with GDPR
              regulations. Your credentials are stored securely.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
