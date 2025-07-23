import Header from "@/components/Header";
import FileUploader from "@/components/FileUploader";
import ChatWindow from "@/components/ChatWindow";

export default function Home() {
    return (
        <main className="flex flex-col h-screen bg-gray-100">
            <Header />
            <div className="flex flex-1 overflow-hidden">
                <aside className="w-full md:w-1/3 lg:w-1/4 bg-white">
                    <FileUploader />
                </aside>
                <section className="flex-1 flex flex-col">
                    <ChatWindow />
                </section>
            </div>
        </main>
    );
}