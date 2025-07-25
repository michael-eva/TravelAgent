import React from 'react';
import Link from 'next/link';

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-blue-100 to-blue-300 p-4">
      <div className="max-w-md text-center bg-white shadow-xl rounded-lg p-8">
        <h1 className="text-4xl font-bold text-blue-600 mb-4">Travel Agent</h1>
        
        <p className="text-gray-700 mb-6">
          Capture your travel memories and share your journey with the world!
        </p>
        
        <div className="space-y-4">
          <Feature 
            title="Upload Pictures" 
            description="Easily upload and pin your travel photos on an interactive map."
          />
          <Feature 
            title="Create Itineraries" 
            description="Build and share your travel routes with friends and family."
          />
          <Feature 
            title="Explore Memories" 
            description="Discover travel experiences from around the globe."
          />
        </div>
        
        <div className="mt-8">
          <Link 
            href="/dashboard" 
            className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-full transition duration-300"
          >
            Get Started
          </Link>
        </div>
      </div>
    </div>
  );
}

function Feature({ title, description }: { title: string, description: string }) {
  return (
    <div className="bg-blue-50 p-4 rounded-md">
      <h3 className="font-semibold text-blue-700 mb-2">{title}</h3>
      <p className="text-gray-600 text-sm">{description}</p>
    </div>
  );
}
