package lx.edu.springmvc.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;


import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;

@Controller
public class MainController {

	@GetMapping("login_form.do")
	public String loginForm() {
		return "login";
	}
	
	
	@PostMapping("login_action.do")
	public String loginAction(HttpServletRequest req,@RequestParam("id") String id,@RequestParam("pw") String pw, HttpSession session) {
		// id, pw 세션에 넣어야함
		System.out.println("id = " + id + ", pw = " + pw);
		if (id.equals(pw)) { // login한 것으로 처리함
			// LoginInterceptor에서 getSession을 사용하기 때문에 session에 id를 집어넣어야함
			// HttpSession session을 매개변수로 사용하여 setAttribute를 하게 함
			session.setAttribute("userId", id);
			return "redirect:addrbook_list.do";
		}
		
		
		return "redirect:login_form.do";
	}
}
