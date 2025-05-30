import streamlit as st
from file_processor import DocumentProcessor
from document_storage import DocumentStorage
import os
import time
from typing import List, Dict, Any

def document_upload_section(user_id: str, memory_system):
    """Sidebar document upload widget"""
    st.sidebar.markdown("### 📄 Knowledge Upload")
    
    # File type explanations
    with st.sidebar.expander("Supported Formats"):
        st.caption("""
        - **PDF**: Text-based documents  
        - **DOCX**: Microsoft Word documents  
        - **CSV/Excel**: Tabular data  
        - **Text/Markdown**: Raw text files  
        """)
    
    # File uploader
    uploaded_files = st.sidebar.file_uploader(
        "Upload documents",
        type=["pdf", "docx", "csv", "txt", "xlsx", "md"],
        accept_multiple_files=True,
        help="Documents become part of your knowledge base"
    )
    
    # Process files
    if uploaded_files and st.sidebar.button('Process Documents', key="process_docs"):
        processor = DocumentProcessor()
        doc_storage = DocumentStorage(memory_system.driver)
        
        progress_bar = st.sidebar.progress(0)
        status_container = st.sidebar.container()
        
        successful_uploads = 0
        
        for i, file in enumerate(uploaded_files):
            try:
                with status_container:
                    st.info(f"Processing {file.name}...")
                
                # Process and store
                chunks = processor.process_file(file, user_id)
                doc_id, chunk_ids = doc_storage.store_document(
                    user_id=user_id, 
                    filename=file.name, 
                    chunks=chunks
                )
                
                with status_container:
                    st.success(f"Added {len(chunks)} chunks from {file.name}")
                
                successful_uploads += 1
                
            except Exception as e:
                with status_container:
                    st.error(f"Failed to process {file.name}: {str(e)}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        # Clear progress and show summary
        progress_bar.empty()
        status_container.empty()
        
        if successful_uploads > 0:
            st.sidebar.success(f"Successfully processed {successful_uploads} documents")
            if successful_uploads < len(uploaded_files):
                st.sidebar.warning(f"{len(uploaded_files) - successful_uploads} documents failed")
        
        # Refresh the page to show new documents
        time.sleep(1)
        st.rerun()

def document_library_interface(user_id: str, memory_system):
    """Main panel document management interface"""
    st.markdown("## 📚 Knowledge Library")
    
    doc_storage = DocumentStorage(memory_system.driver)
    
    # Get document statistics
    stats = doc_storage.get_document_stats(user_id)
    
    # Display stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Documents", stats['total_documents'])
    with col2:
        st.metric("Knowledge Chunks", stats['total_chunks'])
    with col3:
        if stats['total_documents'] > 0:
            avg_chunks = stats['total_chunks'] / stats['total_documents']
            st.metric("Avg Chunks/Doc", f"{avg_chunks:.1f}")
        else:
            st.metric("Avg Chunks/Doc", "0")
    
    # Search functionality
    st.markdown("### 🔍 Search Knowledge")
    search_query = st.text_input(
        "Search through your documents",
        placeholder="Enter keywords to search your knowledge base..."
    )
    
    if search_query:
        search_results = doc_storage.search_documents(user_id, search_query, limit=10)
        
        if search_results:
            st.markdown(f"Found {len(search_results)} relevant chunks:")
            
            for result in search_results:
                with st.expander(f"📄 {result['filename']} (Chunk {result['chunk_index'] + 1})"):
                    st.markdown(f"**Relevance:** {result['similarity']:.2f}")
                    st.markdown("**Content:**")
                    st.write(result['chunk_content'][:500] + "..." if len(result['chunk_content']) > 500 else result['chunk_content'])
                    
                    # Option to use this chunk in conversation
                    if st.button("Use in Chat", key=f"use_{result['doc_id']}_{result['chunk_index']}"):
                        st.session_state.document_context = {
                            "source": f"{result['filename']} (Chunk {result['chunk_index'] + 1})",
                            "content": result['chunk_content']
                        }
                        st.success("Added to conversation context!")
        else:
            st.info("No matching content found in your documents.")
    
    # Document management
    st.markdown("### 📋 Document Management")
    
    documents = doc_storage.get_user_documents(user_id)
    
    if not documents:
        st.info("No documents uploaded yet. Use the sidebar to upload your first document.")
        return
    
    # Document list
    for doc in documents:
        with st.container():
            col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
            
            with col1:
                st.markdown(f"**{doc['filename']}**")
            
            with col2:
                st.markdown(f"{doc['chunk_count']} chunks")
            
            with col3:
                created_date = doc['created_at'].strftime('%Y-%m-%d')
                st.markdown(created_date)
            
            with col4:
                if st.button("🗑️ Delete", key=f"delete_{doc['id']}"):
                    if doc_storage.delete_document(doc['id'], user_id):
                        st.success(f"Deleted {doc['filename']}")
                        st.rerun()
                    else:
                        st.error("Failed to delete document")
            
            # Preview toggle
            if st.toggle(f"Preview {doc['filename']}", key=f"preview_{doc['id']}"):
                preview_document(doc['id'], user_id, doc_storage)
            
            st.markdown("---")

def preview_document(doc_id: str, user_id: str, doc_storage: DocumentStorage):
    """Show document content with conversational integration"""
    chunks = doc_storage.get_document_chunks(doc_id, user_id)
    
    if not chunks:
        st.warning("No content found for this document.")
        return
    
    st.markdown("#### Document Content")
    
    for chunk in chunks:
        with st.expander(f"Chunk {chunk['chunk_index'] + 1}"):
            st.markdown(f"**Source:** {chunk['source']}")
            st.markdown("**Content:**")
            st.write(chunk['content'])
            
            # Context injection button
            if st.button(f"Use in Chat", key=f"use_chunk_{chunk['id']}"):
                st.session_state.document_context = {
                    "source": f"{chunk['source']} (Chunk {chunk['chunk_index'] + 1})",
                    "content": chunk['content']
                }
                st.success("Added to conversation context!")

def get_unified_context_for_chat(user_id: str, query: str, memory_system) -> str:
    """Get unified context combining both memory and document searches"""
    if not hasattr(memory_system, 'driver'):
        return ""
    
    try:
        # Get memory context
        memory_context = []
        try:
            memory_results = memory_system.get_relevant_memories(query, user_id, limit=3)
            memory_context = memory_results if memory_results else []
        except Exception:
            memory_context = []
        
        # Get document context 
        doc_storage = DocumentStorage(memory_system.driver)
        document_results = doc_storage.search_documents(user_id, query, limit=3)
        
        # Build unified context
        context_parts = []
        
        # Add memory context
        if memory_context:
            context_parts.append("From conversation history:")
            for memory in memory_context[:2]:  # Limit to 2 memories
                context_parts.append(f"- {memory[:200]}...")
        
        # Add document context
        if document_results:
            context_parts.append("\nFrom uploaded documents:")
            for result in document_results:
                filename = result.get('filename', 'Unknown Document')
                content = result.get('chunk_content', '')[:300]
                context_parts.append(f"- From {filename}: {content}...")
        
        # If no specific results found, try broader searches
        if not memory_context and not document_results:
            # Try broader document search
            broad_results = doc_storage._get_recent_document_chunks(user_id, limit=2)
            if broad_results:
                context_parts.append("\nRecent document content:")
                for result in broad_results:
                    filename = result.get('filename', 'Unknown Document')
                    content = result.get('chunk_content', '')[:300]
                    context_parts.append(f"- From {filename}: {content}...")
        
        return "\n".join(context_parts) if context_parts else ""
        
    except Exception as e:
        return ""


def get_document_context_for_chat(user_id: str, query: str, memory_system) -> str:
    """Get relevant document context for chat responses - DEPRECATED, use get_unified_context_for_chat"""
    return get_unified_context_for_chat(user_id, query, memory_system)

def display_document_stats_in_sidebar(user_id: str, memory_system):
    """Display document statistics in sidebar"""
    try:
        doc_storage = DocumentStorage(memory_system.driver)
        stats = doc_storage.get_document_stats(user_id)
        
        if stats['total_documents'] > 0:
            st.sidebar.markdown("---")
            st.sidebar.markdown("📊 **Knowledge Stats**")
            st.sidebar.caption(f"Documents: {stats['total_documents']}")
            st.sidebar.caption(f"Knowledge chunks: {stats['total_chunks']}")
    
    except Exception:
        # Silently fail if stats can't be retrieved
        pass