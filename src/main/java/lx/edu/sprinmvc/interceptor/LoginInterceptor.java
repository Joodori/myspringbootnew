package lx.edu.sprinmvc.interceptor;

import org.springframework.web.servlet.HandlerInterceptor;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

public class LoginInterceptor implements HandlerInterceptor {
	
	@Override
	public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
			throws Exception {
		// login 체크 수행
		String userId = (String) request.getSession().getAttribute("userId");
		System.out.println("preHandle() userId = " + userId);
		if (userId!=null && userId.length()>0) {
			return true;
		}
		response.sendRedirect("login_form.do");
		return false;
	}
	
}
