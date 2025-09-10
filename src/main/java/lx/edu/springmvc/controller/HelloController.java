package lx.edu.springmvc.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.RequestMapping;

@Controller
public class HelloController {

	@RequestMapping("/hello.do")
	public String hello() {
		return "hello";
	}
	@RequestMapping("/hello_feat_list2.do")
	public String hello_feat_list2() {
		// feat/edit branch에서 작업
		//ㅇ
		//ㅁㅁ
		//ㅇㅇㅇ
		//ㅁ
		//ㅇㅇ
		//ㅁㅁㅁ
		// 다른 branch에서 각각 ㅇ 과 ㅁ 을지워서 충돌일으키기
		
		
		return "hello";
	}
	
	@RequestMapping("/hello_feat_list.do")
	public String hello_feat_list() {
		return "hello";
	}
	
	
	public void taesu() {
		//씨발진짜 울고싶다 살려줌매
	}
}
