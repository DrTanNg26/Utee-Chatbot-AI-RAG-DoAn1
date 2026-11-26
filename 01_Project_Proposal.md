1. Bối cảnh và Lý do chọn đề tài
Thực trạng tại UTT: Hiện nay, các thông tin liên quan đến sinh viên (quy chế đào tạo tín chỉ, quy định học bổng, khung điểm rèn luyện, hướng dẫn thủ tục một cửa và đề cương chi tiết học phần) nằm phân tán trên nhiều website, cổng thông tin và các tệp văn bản khác nhau.
Khó khăn của sinh viên: Tân sinh viên và sinh viên các khóa gặp nhiều khó khăn khi cần tra cứu nhanh quy định; khó biết văn bản nào đang có hiệu lực mới nhất; hoặc không rõ tình trạng học tập cá nhân liên hệ thế nào với quy chế.
Ý tưởng đề xuất: Nhóm đề xuất xây dựng UTee - một Chatbot AI đóng vai trò như một “người bạn đồng hành kỹ thuật số”, giúp sinh viên giải đáp thắc mắc học vụ qua hội thoại tiếng Việt tự nhiên 24/7.
2. Mục tiêu của Đề tài
Mục tiêu tổng quát: Xây dựng ứng dụng Web Chatbot AI có khả năng trả lời chính xác các câu hỏi về quy định, quy chế của Nhà trường dựa trên tài liệu chính thức, đồng thời hỗ trợ tra cứu dữ liệu học tập cá nhân mô phỏng có phân quyền bảo mật.
Mục tiêu cụ thể: 
	Giao diện trò chuyện trực quan, thân thiện, dễ sử dụng trên nền tảng Web.
	Ứng dụng kỹ thuật RAG để câu trả lời luôn có căn cứ, trích dẫn rõ ràng tên văn bản, số Điều và số Trang, triệt tiêu tình trạng AI bịa đặt.
	Xây dựng cơ sở dữ liệu mô phỏng để sinh viên sau khi đăng nhập có thể xem thông tin học tập cá nhân (điểm, lịch thi, tín chỉ).
	Đảm bảo an toàn thông tin: Sinh viên chỉ được xem thông tin của chính mình.
3. Phạm vi và Các tính năng dự kiến
Hệ thống UTee tập trung vào 2 trụ cột chức năng chính:
1.	Hỏi đáp Quy chế & Học vụ thông minh (Kiến trúc RAG):
	Tra cứu quy chế đào tạo tín chỉ (đăng ký học phần, cảnh báo học vụ, hoãn thi, điều kiện tốt nghiệp).
	Tra cứu tiêu chuẩn xét cấp học bổng khuyến khích học tập và các chính sách miễn giảm học phí.
	Hướng dẫn đánh giá điểm rèn luyện và các thủ tục hành chính sinh viên.
	Tra cứu thông tin đề cương chi tiết, số tín chỉ và học phần tiên quyết của ngành học.
	Cơ chế an toàn: Khi gặp câu hỏi nằm ngoài phạm vi quy chế Nhà trường, Chatbot sẽ lịch sự từ chối và hướng dẫn sinh viên liên hệ phòng ban chuyên môn.
2.	Tra cứu Thông tin Học tập Cá nhân hóa:
	Đăng nhập xác thực tài khoản sinh viên.
	Xem điểm tổng kết các học phần đã tích lũy và kiểm tra các môn cần học lại/cải thiện.
	Xem thời khóa biểu và lịch thi cá nhân trong kỳ.
4. Định hướng Kiến trúc & Công nghệ dự kiến
-	Giao diện (Frontend): Ứng dụng Web (React/HTML-CSS-JS hiện đại), hỗ trợ hiển thị Markdown và các thẻ trích dẫn nguồn tài liệu.
-	Máy chủ ứng dụng (Backend): Python FastAPI - xử lý logic đăng nhập, xác thực JWT và điều phối luồng trò chuyện.
-	Cơ sở dữ liệu (Database): SQLite/CSDL quan hệ - lưu trữ tài khoản sinh viên mô phỏng, lịch sử đoạn chat và dữ liệu điểm số.
-	Module Trí tuệ nhân tạo (AI Engine): Mô hình ngôn ngữ lớn (LLM) kết hợp Vector Database (FAISS) để lưu trữ và truy xuất các đoạn văn bản quy chế UTT.
